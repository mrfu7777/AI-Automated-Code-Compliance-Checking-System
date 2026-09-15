from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, TypedDict
from uuid import UUID

from fastapi.concurrency import run_in_threadpool
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Clause,
    DocumentPage,
    Evidence,
    FileVersion,
    Project,
    ProjectFact,
    ProjectFile,
    Rule,
    RulePack,
    Standard,
    StandardVersion,
)
from app.services.storage import ObjectStorage

DEMO_PROJECT_CODE = "DEMO-V1-FIRE"
DEMO_STANDARD_CODE = "DEMO-FIRE-001"
DEMO_RULE_PACK_VERSION = "1.0.0"


@dataclass(frozen=True)
class DemoScenario:
    created: bool
    project: Project
    rule_pack: RulePack


class DemoRuleSpec(TypedDict):
    number: str
    code: str
    title: str
    severity: str
    text: str
    fact: str
    expression: dict[str, Any]
    unit: str | None


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _pdf(title: str, lines: list[str], *, draw_plan: bool = False) -> bytes:
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    width, height = A4
    canvas.setTitle(title)
    canvas.setFont("Helvetica-Bold", 16)
    canvas.drawString(48, height - 52, title)
    canvas.setFont("Helvetica", 10)
    y = height - 80
    for line in lines:
        canvas.drawString(48, y, line)
        y -= 16
    if draw_plan:
        canvas.rect(80, 260, width - 160, 310)
        canvas.line(width / 2, 260, width / 2, 570)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(120, 520, "OPEN OFFICE")
        canvas.drawString(width / 2 + 45, 520, "MEETING")
        canvas.setLineWidth(4)
        canvas.line(80, 310, 80, 365)
        canvas.setLineWidth(1)
        canvas.drawString(92, 330, "Exit A: 1.20 m")
        canvas.drawString(92, 290, "Only one verified exit in this synthetic scenario")
    canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def _page_image(title: str, lines: list[str], *, draw_plan: bool = False) -> bytes:
    image = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((15, 15, 1185, 785), outline="#243447", width=3)
    draw.text((45, 38), title, fill="#102a43")
    y = 78
    for line in lines:
        draw.text((45, y), line, fill="#334e68")
        y += 28
    if draw_plan:
        draw.rectangle((110, 230, 1090, 690), outline="#334e68", width=4)
        draw.line((600, 230, 600, 690), fill="#334e68", width=3)
        draw.line((110, 570, 110, 650), fill="#d64545", width=12)
        draw.text((135, 585), "EXIT A / CLEAR WIDTH 1.20 m", fill="#d64545")
        draw.text((135, 650), "ONE VERIFIED EXIT", fill="#d64545")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


async def _upload(
    storage: ObjectStorage, object_key: str, content: bytes, media_type: str
) -> None:
    await run_in_threadpool(
        storage.upload, object_key, io.BytesIO(content), len(content), media_type
    )


async def _existing_scenario(
    session: AsyncSession, organization_id: UUID
) -> DemoScenario | None:
    project = await session.scalar(
        select(Project).where(
            Project.organization_id == organization_id,
            Project.code == DEMO_PROJECT_CODE,
        )
    )
    if project is None:
        return None
    rule_pack = await session.scalar(
        select(RulePack)
        .join(StandardVersion)
        .join(Standard)
        .where(
            Standard.organization_id == organization_id,
            Standard.code == DEMO_STANDARD_CODE,
            RulePack.semantic_version == DEMO_RULE_PACK_VERSION,
        )
    )
    if rule_pack is None:
        raise RuntimeError("The demo scenario is incomplete; restore or reset the demo database")
    return DemoScenario(created=False, project=project, rule_pack=rule_pack)


async def create_demo_scenario(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    organization_id: UUID,
    actor_id: UUID,
) -> DemoScenario:
    existing = await _existing_scenario(session, organization_id)
    if existing is not None:
        return existing

    project = Project(
        organization_id=organization_id,
        name="[DEMO] Existing Office Renovation",
        code=DEMO_PROJECT_CODE,
        jurisdiction="Synthetic training jurisdiction",
        design_date=date(2026, 1, 15),
        building_type="Existing office renovation",
        status="active",
    )
    session.add(project)
    await session.flush()

    regulation_lines = [
        "SYNTHETIC TRAINING MATERIAL - NOT A REAL REGULATION",
        "D1 Exit count: the demo floor shall have at least two exits.",
        "D2 Exit width: the demo exit clear width shall be at least 1.10 m.",
        "D3 Height: the demo building height shall not exceed 24 m.",
        "D4 Compartment: the demo compartment area shall not exceed 2500 square metres.",
    ]
    drawing_lines = [
        "SYNTHETIC TRAINING DRAWING - NOT FOR CONSTRUCTION",
        "Building height: 21 m",
        "Verified exits on this floor: 1",
        "Exit A clear width: 1.20 m",
        "Fire compartment area: not provided",
    ]
    regulation_pdf = _pdf("Synthetic Fire Review Standard", regulation_lines)
    drawing_pdf = _pdf("Synthetic Existing Office Plan", drawing_lines, draw_plan=True)
    regulation_png = _page_image("Synthetic Fire Review Standard", regulation_lines)
    drawing_png = _page_image("Synthetic Existing Office Plan", drawing_lines, draw_plan=True)
    prefix = f"organizations/{organization_id}/demo/v1"
    regulation_key = f"{prefix}/synthetic-fire-standard.pdf"
    drawing_key = f"{prefix}/synthetic-office-plan.pdf"
    regulation_image_key = f"{prefix}/synthetic-fire-standard-page-1.png"
    drawing_image_key = f"{prefix}/synthetic-office-plan-page-1.png"
    await _upload(storage, regulation_key, regulation_pdf, "application/pdf")
    await _upload(storage, drawing_key, drawing_pdf, "application/pdf")
    await _upload(storage, regulation_image_key, regulation_png, "image/png")
    await _upload(storage, drawing_image_key, drawing_png, "image/png")

    regulation_file = ProjectFile(
        project_id=project.id,
        logical_name="Synthetic fire review standard",
        purpose="regulation_source",
    )
    drawing_file = ProjectFile(
        project_id=project.id,
        logical_name="Synthetic existing office plan",
        purpose="project_drawing",
    )
    session.add_all([regulation_file, drawing_file])
    await session.flush()
    regulation_version = FileVersion(
        project_file_id=regulation_file.id,
        version_number=1,
        original_filename="synthetic-fire-standard.pdf",
        media_type="application/pdf",
        size_bytes=len(regulation_pdf),
        sha256=_sha256(regulation_pdf),
        object_key=regulation_key,
        uploaded_by_id=actor_id,
    )
    drawing_version = FileVersion(
        project_file_id=drawing_file.id,
        version_number=1,
        original_filename="synthetic-existing-office-plan.pdf",
        media_type="application/pdf",
        size_bytes=len(drawing_pdf),
        sha256=_sha256(drawing_pdf),
        object_key=drawing_key,
        uploaded_by_id=actor_id,
    )
    session.add_all([regulation_version, drawing_version])
    await session.flush()
    regulation_page = DocumentPage(
        file_version_id=regulation_version.id,
        page_number=1,
        width=595,
        height=842,
        extraction_method="synthetic_demo",
        text="\n".join(regulation_lines),
        char_count=len("\n".join(regulation_lines)),
        average_confidence=1,
        image_object_key=regulation_image_key,
    )
    drawing_page = DocumentPage(
        file_version_id=drawing_version.id,
        page_number=1,
        width=1200,
        height=800,
        extraction_method="synthetic_demo",
        text="\n".join(drawing_lines),
        char_count=len("\n".join(drawing_lines)),
        average_confidence=1,
        image_object_key=drawing_image_key,
    )
    session.add_all([regulation_page, drawing_page])
    await session.flush()

    standard = Standard(
        organization_id=organization_id,
        code=DEMO_STANDARD_CODE,
        title="Synthetic Fire Safety Demonstration Standard",
        jurisdiction="Synthetic training jurisdiction",
    )
    session.add(standard)
    await session.flush()
    standard_version = StandardVersion(
        standard_id=standard.id,
        edition="2026-demo",
        effective_from=date(2026, 1, 1),
        lifecycle_status="published",
        source_file_version_id=regulation_version.id,
        document_hash=regulation_version.sha256,
        parser_version="m8.synthetic-demo.v1",
    )
    session.add(standard_version)
    await session.flush()

    rule_specs: list[DemoRuleSpec] = [
        {
            "number": "D1",
            "code": "DEMO-EXIT-COUNT",
            "title": "At least two exits",
            "severity": "critical",
            "text": regulation_lines[1],
            "fact": "exit.count",
            "expression": {"op": "gte", "fact": "exit.count", "value": 2},
            "unit": None,
        },
        {
            "number": "D2",
            "code": "DEMO-EXIT-WIDTH",
            "title": "Exit clear width",
            "severity": "high",
            "text": regulation_lines[2],
            "fact": "egress.door_clear_width_m",
            "expression": {
                "op": "gte",
                "fact": "egress.door_clear_width_m",
                "value": 1.1,
                "unit": "m",
            },
            "unit": "m",
        },
        {
            "number": "D3",
            "code": "DEMO-BUILDING-HEIGHT",
            "title": "Building height limit",
            "severity": "high",
            "text": regulation_lines[3],
            "fact": "building.height_m",
            "expression": {
                "op": "lte",
                "fact": "building.height_m",
                "value": 24,
                "unit": "m",
            },
            "unit": "m",
        },
        {
            "number": "D4",
            "code": "DEMO-COMPARTMENT-AREA",
            "title": "Fire compartment area",
            "severity": "critical",
            "text": regulation_lines[4],
            "fact": "fire_compartment.area_m2",
            "expression": {
                "op": "lte",
                "fact": "fire_compartment.area_m2",
                "value": 2500,
                "unit": "m2",
            },
            "unit": "m2",
        },
    ]
    clauses: list[Clause] = []
    for index, spec in enumerate(rule_specs, start=1):
        clause = Clause(
            standard_version_id=standard_version.id,
            source_page_id=regulation_page.id,
            clause_number=str(spec["number"]),
            level="article",
            heading=str(spec["title"]),
            original_text=str(spec["text"]),
            page_number=1,
            bounding_box={"x0": 40, "y0": 80 + index * 20, "x1": 555, "y1": 98 + index * 20},
            confidence=1,
            reviewed_by_id=actor_id,
            reviewed_at=datetime.now(UTC),
            order_index=index,
            lifecycle_status="published",
        )
        session.add(clause)
        clauses.append(clause)
    await session.flush()
    for clause in clauses:
        session.add(
            Evidence(
                organization_id=organization_id,
                clause_id=clause.id,
                file_version_id=regulation_version.id,
                kind="document_region",
                location={"page": 1, "bbox": clause.bounding_box},
                excerpt=clause.original_text,
                created_by_id=actor_id,
            )
        )

    rule_pack = RulePack(
        standard_version_id=standard_version.id,
        name="Synthetic V1 Fire Review Rules",
        semantic_version=DEMO_RULE_PACK_VERSION,
        lifecycle_status="published",
        content_hash=_sha256(json.dumps(rule_specs, sort_keys=True).encode()),
        authority_level="project",
        published_at=datetime.now(UTC),
        published_by_id=actor_id,
    )
    session.add(rule_pack)
    await session.flush()
    for clause, spec in zip(clauses, rule_specs, strict=True):
        session.add(
            Rule(
                rule_pack_id=rule_pack.id,
                source_clause_id=clause.id,
                code=str(spec["code"]),
                title=str(spec["title"]),
                severity=str(spec["severity"]),
                lifecycle_status="published",
                applicability={},
                inputs=[
                    {
                        "fact_key": str(spec["fact"]),
                        "required": True,
                        "expected_unit": spec["unit"],
                    }
                ],
                expression=dict(spec["expression"]),
                missing_data_status="insufficient_information",
                reviewed_by_id=actor_id,
                reviewed_at=datetime.now(UTC),
            )
        )

    fact_specs = [
        ("exit.count", 1, None, "Verified one exit on the synthetic plan"),
        ("egress.door_clear_width_m", 1.2, "m", "Exit A width label"),
        ("building.height_m", 21, "m", "Synthetic project note"),
    ]
    for key, value, unit, excerpt in fact_specs:
        fact = ProjectFact(
            project_id=project.id,
            key=key,
            value=value,
            unit=unit,
            scope_data={"floor": "demo-floor"},
            source="synthetic_demo",
            verification_status="verified",
            confidence=1,
            extractor_version="m8.synthetic-demo.v1",
            verified_by_id=actor_id,
            verified_at=datetime.now(UTC),
        )
        session.add(fact)
        await session.flush()
        session.add(
            Evidence(
                organization_id=organization_id,
                project_fact_id=fact.id,
                file_version_id=drawing_version.id,
                kind="image_region",
                location={"page": 1, "bbox": {"x0": 100, "y0": 220, "x1": 1100, "y1": 700}},
                excerpt=excerpt,
                created_by_id=actor_id,
            )
        )
    await session.commit()
    await session.refresh(project)
    await session.refresh(rule_pack)
    return DemoScenario(created=True, project=project, rule_pack=rule_pack)
