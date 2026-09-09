import asyncio
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.db.models import AuditEvent, FileVersion, Organization, User
from app.domain.enums import JobStatus
from app.tasks import file_processing


def _create_project(client):  # type: ignore[no-untyped-def]
    response = client.post(
        "/api/v1/projects",
        json={
            "name": "Old Factory Renovation",
            "code": "OFR-001",
            "jurisdiction": "Shanghai",
        },
        headers={"X-Request-ID": "create-project-001"},
    )
    assert response.status_code == 201
    return response.json()


def test_project_creation_and_listing_are_persistent_and_audited(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, _storage, _dispatcher, session_factory = m1_environment
    project = _create_project(client)

    listing = client.get("/api/v1/projects")
    detail = client.get(f"/api/v1/projects/{project['id']}")

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [project["id"]]
    assert detail.json()["name"] == "Old Factory Renovation"

    async def audit_count() -> int:
        async with session_factory() as session:
            return await session.scalar(select(func.count()).select_from(AuditEvent)) or 0

    assert asyncio.run(audit_count()) == 1


def test_pdf_upload_creates_immutable_versions_and_job(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, storage, dispatcher, _session_factory = m1_environment
    project = _create_project(client)
    first_pdf = b"%PDF-1.7\nfirst version"
    second_pdf = b"%PDF-1.7\nsecond version"

    first = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "Existing floor plan"},
        files={"upload": ("plan.pdf", first_pdf, "application/pdf")},
        headers={"X-Request-ID": "upload-001"},
    )
    second = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "Existing floor plan"},
        files={"upload": ("plan-revised.pdf", second_pdf, "application/pdf")},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()
    second_body = second.json()
    assert first_body["project_file"]["id"] == second_body["project_file"]["id"]
    assert first_body["file_version"]["version_number"] == 1
    assert second_body["file_version"]["version_number"] == 2
    assert first_body["file_version"]["sha256"] == sha256(first_pdf).hexdigest()
    assert first_body["job"]["status"] == "queued"
    assert first_body["job"]["request_id"] == "upload-001"
    assert len(storage.objects) == 2
    assert len(dispatcher.job_ids) == 2

    files = client.get(f"/api/v1/projects/{project['id']}/files")
    jobs = client.get(f"/api/v1/projects/{project['id']}/jobs")
    assert files.status_code == 200
    assert [version["version_number"] for version in files.json()[0]["versions"]] == [2, 1]
    assert jobs.status_code == 200
    assert len(jobs.json()) == 2

    download = client.get(
        f"/api/v1/file-versions/{first_body['file_version']['id']}/download"
    )
    assert download.status_code == 200
    assert download.json()["expires_in_seconds"] == 900


def test_upload_validation_rejects_unsupported_and_invalid_files(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, storage, _dispatcher, _session_factory = m1_environment
    project = _create_project(client)

    text_response = client.post(
        f"/api/v1/projects/{project['id']}/files",
        files={"upload": ("notes.txt", b"notes", "text/plain")},
    )
    fake_pdf_response = client.post(
        f"/api/v1/projects/{project['id']}/files",
        files={"upload": ("fake.pdf", b"not a pdf", "application/pdf")},
    )

    assert text_response.status_code == 415
    assert text_response.json()["error"]["code"] == "unsupported_file_type"
    assert fake_pdf_response.status_code == 422
    assert fake_pdf_response.json()["error"]["code"] == "invalid_pdf"
    assert storage.objects == {}


def test_dispatch_failure_is_visible_and_retryable(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, _storage, dispatcher, _session_factory = m1_environment
    project = _create_project(client)
    dispatcher.fail = True
    upload = client.post(
        f"/api/v1/projects/{project['id']}/files",
        files={"upload": ("plan.pdf", b"%PDF-1.7\ndata", "application/pdf")},
    )
    job = upload.json()["job"]
    assert job["status"] == "failed"
    assert job["error_data"]["code"] == "dispatch_failed"

    dispatcher.fail = False
    retry = client.post(
        f"/api/v1/jobs/{job['id']}/retry",
        headers={"X-Request-ID": "retry-001"},
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "queued"
    assert retry.json()["request_id"] == "retry-001"
    assert dispatcher.job_ids == [UUID(job["id"])]

    second_retry = client.post(f"/api/v1/jobs/{job['id']}/retry")
    assert second_retry.status_code == 409
    assert second_retry.json()["error"]["code"] == "job_not_retryable"


def test_worker_completes_metadata_job(m1_environment, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client, storage, _dispatcher, session_factory = m1_environment
    project = _create_project(client)
    upload = client.post(
        f"/api/v1/projects/{project['id']}/files",
        files={"upload": ("plan.pdf", b"%PDF-1.7\nworker", "application/pdf")},
    ).json()
    job_id = upload["job"]["id"]
    monkeypatch.setattr(file_processing, "async_session_factory", session_factory)
    monkeypatch.setattr(file_processing, "get_object_storage", lambda: storage)

    asyncio.run(file_processing.run_file_processing_job(UUID(job_id)))
    response = client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == JobStatus.SUCCEEDED
    assert result["progress"] == 1
    assert result["attempts"] == 1
    assert result["output_data"]["processor"] == "m1.file-metadata.v1"

    async def read_version_count() -> int:
        async with session_factory() as session:
            return await session.scalar(select(func.count()).select_from(FileVersion)) or 0

    assert asyncio.run(read_version_count()) == 1


def test_project_access_is_scoped_to_the_actor_organization(m1_environment) -> None:  # type: ignore[no-untyped-def]
    client, _storage, _dispatcher, session_factory = m1_environment
    project = _create_project(client)
    other_organization_id = uuid4()
    other_user_id = uuid4()

    async def seed_other_actor() -> None:
        async with session_factory() as session:
            session.add(
                Organization(
                    id=other_organization_id,
                    name="Another Practice",
                    slug=f"another-practice-{other_organization_id}",
                )
            )
            session.add(
                User(
                    id=other_user_id,
                    organization_id=other_organization_id,
                    email=f"architect-{other_user_id}@example.invalid",
                    display_name="Another Architect",
                    role="architect",
                    is_active=True,
                )
            )
            await session.commit()

    asyncio.run(seed_other_actor())
    headers = {"X-User-ID": str(other_user_id)}

    assert client.get("/api/v1/projects", headers=headers).json() == []
    detail = client.get(f"/api/v1/projects/{project['id']}", headers=headers)
    assert detail.status_code == 404
    assert detail.json()["error"]["code"] == "project_not_found"
