import asyncio
from uuid import UUID

from sqlalchemy import func, select

from app.db.models import Clause, ClauseRevision, DocumentPage


def _create_source(client):  # type: ignore[no-untyped-def]
    project = client.post("/api/v1/projects", json={"name": "Code Library"}).json()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "GB 55037-2022", "purpose": "regulation_source"},
        files={"upload": ("gb55037.pdf", b"%PDF-1.7\nsource", "application/pdf")},
    ).json()
    return project, upload


def test_ingestion_reuses_m1_file_and_generic_job_pipeline(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, _storage, dispatcher, _session_factory = m1_environment
    project, upload = _create_source(client)
    response = client.post(
        "/api/v1/regulations/ingestions",
        json={
            "file_version_id": upload["file_version"]["id"],
            "code": "GB 55037-2022",
            "title": "General Code for Fire Protection of Buildings",
            "edition": "2022",
            "jurisdiction": "China",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["version"]["source_file_version_id"] == upload["file_version"]["id"]
    assert body["version"]["document_hash"] == upload["file_version"]["sha256"]
    assert body["job"]["project_id"] == project["id"]
    assert dispatcher.dispatched[-1][1] == "regulation.parse"
    assert len(client.get("/api/v1/regulations").json()[0]["versions"]) == 1

    duplicate = client.post(
        "/api/v1/regulations/ingestions",
        json={
            "file_version_id": upload["file_version"]["id"],
            "code": "GB 55037-2022",
            "title": "Same",
            "edition": "2022",
            "jurisdiction": "China",
        },
    )
    assert duplicate.status_code == 409


def test_clause_correction_search_split_merge_publish_and_page_link(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, storage, _dispatcher, session_factory = m1_environment
    _project, upload = _create_source(client)
    ingestion = client.post(
        "/api/v1/regulations/ingestions",
        json={
            "file_version_id": upload["file_version"]["id"],
            "code": "GB 55037-2022",
            "title": "Fire Code",
            "edition": "2022",
            "jurisdiction": "China",
        },
    ).json()
    version_id = UUID(ingestion["version"]["id"])
    file_version_id = UUID(upload["file_version"]["id"])

    async def seed() -> tuple[UUID, UUID]:
        async with session_factory() as session:
            page = DocumentPage(
                file_version_id=file_version_id,
                page_number=7,
                width=600,
                height=800,
                extraction_method="ocr",
                text="6.4.1 疏散楼梯",
                char_count=10,
                average_confidence=0.91,
                image_object_key="page-7.png",
            )
            session.add(page)
            await session.flush()
            first = Clause(
                standard_version_id=version_id,
                source_page_id=page.id,
                clause_number="6.4.1",
                level="article",
                original_text="6.4.1 old text",
                page_number=7,
                bounding_box={"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                confidence=0.91,
                order_index=1,
                lifecycle_status="draft",
            )
            second = Clause(
                standard_version_id=version_id,
                source_page_id=page.id,
                clause_number="6.4.2",
                level="article",
                original_text="6.4.2 second",
                page_number=7,
                bounding_box={"x0": 1, "y0": 5, "x1": 3, "y1": 6},
                confidence=0.90,
                order_index=2,
                lifecycle_status="draft",
            )
            session.add_all([first, second])
            await session.commit()
            return first.id, second.id

    first_id, second_id = asyncio.run(seed())
    storage.objects["page-7.png"] = b"png"
    pages = client.get(f"/api/v1/regulations/versions/{version_id}/pages").json()
    assert pages[0]["image_url"].startswith("https://storage.invalid/")
    found = client.get(
        f"/api/v1/regulations/versions/{version_id}/clauses", params={"query": "6.4.1"}
    )
    assert [item["clause_number"] for item in found.json()] == ["6.4.1"]

    corrected = client.patch(
        f"/api/v1/regulations/clauses/{first_id}",
        json={
            "original_text": "6.4.1 corrected text",
            "change_reason": "OCR correction",
        },
    )
    assert corrected.status_code == 200
    assert corrected.json()["lifecycle_status"] == "reviewed"

    split = client.post(
        f"/api/v1/regulations/clauses/{second_id}/split",
        json={
            "first_text": "6.4.2 first half",
            "second_number": "6.4.3",
            "second_text": "6.4.3 second half",
            "change_reason": "Two articles were joined",
        },
    )
    assert split.status_code == 200
    second_half_id = split.json()[1]["id"]
    merged = client.post(
        "/api/v1/regulations/clauses/merge",
        json={
            "clause_ids": [str(second_id), second_half_id],
            "target_number": "6.4.2",
            "merged_text": "6.4.2 reviewed merged text",
            "change_reason": "Reviewer decision",
        },
    )
    assert merged.status_code == 200

    publish = client.post(f"/api/v1/regulations/versions/{version_id}/publish")
    assert publish.status_code == 200
    assert publish.json()["lifecycle_status"] == "published"
    blocked = client.post(f"/api/v1/regulations/versions/{version_id}/reparse")
    assert blocked.status_code == 409

    async def revision_count() -> int:
        async with session_factory() as session:
            return await session.scalar(select(func.count()).select_from(ClauseRevision)) or 0

    assert asyncio.run(revision_count()) == 4


def test_draft_reparse_reuses_generic_dispatcher(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, _storage, dispatcher, _session_factory = m1_environment
    _project, upload = _create_source(client)
    version = client.post(
        "/api/v1/regulations/ingestions",
        json={
            "file_version_id": upload["file_version"]["id"],
            "code": "LOCAL-1",
            "title": "Local Code",
            "edition": "1",
            "jurisdiction": "Local",
        },
    ).json()["version"]
    response = client.post(f"/api/v1/regulations/versions/{version['id']}/reparse")
    assert response.status_code == 200
    assert dispatcher.dispatched[-1][1] == "regulation.parse"
