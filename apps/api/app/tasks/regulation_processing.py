from __future__ import annotations

import asyncio
import io
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Clause, DocumentPage, Evidence, FileVersion, Job, StandardVersion
from app.db.session import async_session_factory, engine
from app.services.job_runtime import run_persisted_job
from app.services.pdf_extraction import PdfiumRegulationExtractor
from app.services.regulation_parser import parse_clause_tree
from app.services.storage import get_object_storage
from app.tasks.celery_app import celery_app

PARSER_VERSION = "m2.pdfium-rapidocr.v1"


async def _parse_regulation(session: AsyncSession, job: Job) -> dict[str, object]:
    standard_version_id = UUID(str(job.input_data["standard_version_id"]))
    standard_version = await session.get(StandardVersion, standard_version_id)
    if standard_version is None:
        raise ValueError(f"Standard version {standard_version_id} does not exist")
    if standard_version.lifecycle_status == "published":
        raise ValueError("Published standard versions cannot be reparsed")
    file_version = await session.get(FileVersion, standard_version.source_file_version_id)
    if file_version is None:
        raise ValueError("The regulation source file no longer exists")

    storage = get_object_storage()
    pages = PdfiumRegulationExtractor(storage).extract(file_version.object_key)
    candidates = parse_clause_tree(pages)
    if not candidates:
        raise ValueError("No numbered clauses were found; manual source inspection is required")

    page_rows: dict[int, DocumentPage] = {}
    for page in pages:
        image_key = f"{file_version.object_key}.pages/{page.page_number}.png"
        storage.upload(image_key, io.BytesIO(page.image_png), len(page.image_png), "image/png")
        row = DocumentPage(
            file_version_id=file_version.id,
            page_number=page.page_number,
            width=page.width,
            height=page.height,
            extraction_method=page.method,
            text="\n".join(line.text for line in page.lines),
            char_count=sum(len(line.text) for line in page.lines),
            average_confidence=(
                sum(line.confidence for line in page.lines) / len(page.lines)
                if page.lines
                else None
            ),
            image_object_key=image_key,
        )
        session.add(row)
        page_rows[page.page_number] = row
    await session.flush()

    clause_rows: dict[str, Clause] = {}
    for order, candidate in enumerate(candidates):
        parent = clause_rows.get(candidate.parent_number or "")
        clause = Clause(
            standard_version_id=standard_version.id,
            parent_id=parent.id if parent else None,
            source_page_id=page_rows[candidate.page_number].id,
            clause_number=candidate.number,
            level=candidate.level,
            heading=candidate.heading,
            original_text=candidate.text,
            page_number=candidate.page_number,
            bounding_box=candidate.bbox,
            confidence=candidate.confidence,
            order_index=order,
            lifecycle_status="draft",
        )
        session.add(clause)
        await session.flush()
        clause_rows[candidate.number] = clause
        session.add(
            Evidence(
                organization_id=job.organization_id,
                clause_id=clause.id,
                file_version_id=file_version.id,
                kind="document_region",
                location={"page": candidate.page_number, "bbox": candidate.bbox},
                excerpt=candidate.text,
            )
        )
    standard_version.parser_version = PARSER_VERSION
    job.progress = 0.95
    await session.flush()
    return {
        "processor": PARSER_VERSION,
        "standard_version_id": str(standard_version.id),
        "page_count": len(pages),
        "clause_count": len(candidates),
        "ocr_page_count": sum(page.method == "ocr" for page in pages),
    }


async def run_regulation_processing_job(job_id: UUID) -> None:
    await run_persisted_job(
        async_session_factory,
        job_id,
        _parse_regulation,
        error_code="regulation_processing_failed",
    )


async def _run_and_dispose(job_id: UUID) -> None:
    try:
        await run_regulation_processing_job(job_id)
    finally:
        await engine.dispose()


@celery_app.task(name="regulations.parse")  # type: ignore[untyped-decorator]
def process_regulation(job_id: str) -> None:
    asyncio.run(_run_and_dispose(UUID(job_id)))
