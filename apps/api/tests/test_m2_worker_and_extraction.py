import asyncio
from types import SimpleNamespace
from uuid import UUID

from PIL import Image
from sqlalchemy import func, select

from app.db.models import Clause, DocumentPage, Evidence, Job
from app.services.pdf_extraction import PdfiumRegulationExtractor
from app.services.regulation_parser import ExtractedPage, TextLine
from app.tasks import regulation_processing


def test_regulation_worker_persists_pages_clauses_and_evidence(m1_environment, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client, storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Code Library"}).json()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/files",
        files={"upload": ("code.pdf", b"%PDF-1.7\nsource", "application/pdf")},
    ).json()
    ingestion = client.post(
        "/api/v1/regulations/ingestions",
        json={
            "file_version_id": upload["file_version"]["id"],
            "code": "GB-TEST",
            "title": "Test Code",
            "edition": "2026",
            "jurisdiction": "China",
        },
    ).json()
    job_id = UUID(ingestion["job"]["id"])
    box = {"x0": 10.0, "y0": 20.0, "x1": 300.0, "y1": 40.0, "origin": "bottom-left"}
    pages = [
        ExtractedPage(
            1,
            600,
            800,
            "ocr",
            [
                TextLine("第一章 总则", box, 0.95),
                TextLine("1.0.1 建筑应安全。", box, 0.91),
            ],
            b"png",
        )
    ]

    class FakeExtractor:
        def __init__(self, supplied_storage):  # type: ignore[no-untyped-def]
            assert supplied_storage is storage

        def extract(self, object_key):  # type: ignore[no-untyped-def]
            assert object_key in storage.objects
            return pages

    monkeypatch.setattr(regulation_processing, "async_session_factory", session_factory)
    monkeypatch.setattr(regulation_processing, "get_object_storage", lambda: storage)
    monkeypatch.setattr(regulation_processing, "PdfiumRegulationExtractor", FakeExtractor)
    asyncio.run(regulation_processing.run_regulation_processing_job(job_id))

    async def counts():  # type: ignore[no-untyped-def]
        async with session_factory() as session:
            job = await session.get_one(Job, job_id)
            return (
                job,
                await session.scalar(select(func.count()).select_from(DocumentPage)),
                await session.scalar(select(func.count()).select_from(Clause)),
                await session.scalar(select(func.count()).select_from(Evidence)),
            )

    job, page_count, clause_count, evidence_count = asyncio.run(counts())
    assert job.status == "succeeded"
    assert job.output_data["ocr_page_count"] == 1
    assert (page_count, clause_count, evidence_count) == (1, 2, 2)


class _FakeTextPage:
    def __init__(self, text: str) -> None:
        self.text = text

    def count_chars(self) -> int:
        return len(self.text)

    def get_text_range(self, index: int, count: int) -> str:
        return self.text[index : index + count]

    def get_charbox(self, index: int):  # type: ignore[no-untyped-def]
        x = float(index % 20) * 5
        return (x, 700.0, x + 4, 712.0)


class _FakeBitmap:
    def to_pil(self) -> Image.Image:
        return Image.new("RGB", (200, 300), "white")


class _FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def get_size(self):  # type: ignore[no-untyped-def]
        return (100.0, 150.0)

    def render(self, scale: int):  # type: ignore[no-untyped-def]
        assert scale == 2
        return _FakeBitmap()

    def get_textpage(self) -> _FakeTextPage:
        return _FakeTextPage(self.text)


class _FakeOcr:
    def __call__(self, image: bytes):
        assert image.startswith(b"\x89PNG")
        return SimpleNamespace(
            boxes=[[[20, 40], [180, 40], [180, 80], [20, 80]]],
            txts=["2.0.1 OCR clause"],
            scores=[0.87],
        )


def test_pdf_extractor_uses_text_layer_and_ocr_fallback(m1_environment, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _client, storage, _dispatcher, _factory = m1_environment
    storage.objects["source.pdf"] = b"pdf"
    document = [_FakePage("1.0.1 " + "A" * 45 + "\ncontinuation"), _FakePage("scan")]
    monkeypatch.setattr("app.services.pdf_extraction.pdfium.PdfDocument", lambda _path: document)

    pages = PdfiumRegulationExtractor(storage, _FakeOcr()).extract("source.pdf")  # type: ignore[arg-type]

    assert [page.method for page in pages] == ["text_layer", "ocr"]
    assert pages[0].lines[0].confidence == 1.0
    assert pages[1].lines[0].text == "2.0.1 OCR clause"
    assert pages[1].lines[0].bbox["origin"] == "bottom-left"
