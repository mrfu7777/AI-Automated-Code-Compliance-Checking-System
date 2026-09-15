import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import CheckResult, CheckRun, Job, PilotFeedback, ReviewPackage, User
from app.services.job_runtime import run_persisted_job
from app.services.model_resilience import (
    ExternalModelRateLimited,
    ExternalModelUnavailable,
    ModelCallGuard,
)


def test_security_headers_and_production_configuration_guard(
    m1_environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _storage, _dispatcher, _session_factory = m1_environment
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert client.get("/api/v1/ready").json() == {
        "status": "ready",
        "database": "reachable",
    }

    from app.main import create_application

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "development")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        create_application()
    monkeypatch.setenv("DEMO_MODE_ENABLED", "true")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="DEMO_MODE_ENABLED"):
        create_application()
    monkeypatch.setenv("DEMO_MODE_ENABLED", "false")
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "too-short")
    monkeypatch.setenv("API_KEY_PEPPER", "too-short")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="secrets"):
        create_application()
    bootstrap_key = "b" * 40
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "api_key")
    monkeypatch.setenv("BOOTSTRAP_API_KEY", bootstrap_key)
    get_settings.cache_clear()
    try:
        response = client.get(
            "/api/v1/operations/overview",
            headers={"Authorization": f"Bearer {bootstrap_key}"},
        )
        assert response.status_code == 200
    finally:
        monkeypatch.setenv("AUTH_MODE", "development")
    get_settings.cache_clear()


def test_api_key_lifecycle_and_viewer_write_block(
    m1_environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Secure pilot"}).json()
    created = client.post(
        "/api/v1/access/api-keys",
        json={
            "name": "Pilot client",
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert created.status_code == 201
    credential = created.json()
    assert credential["token"].startswith("cc_")
    assert credential["token"] not in str(client.get("/api/v1/access/api-keys").json())
    assert (
        client.post(
            "/api/v1/access/api-keys",
            json={"name": "Ambiguous expiry", "expires_at": "2027-01-01T00:00:00"},
        ).status_code
        == 422
    )

    monkeypatch.setenv("AUTH_MODE", "api_key")
    get_settings.cache_clear()
    try:
        authorization = {"Authorization": f"Bearer {credential['token']}"}
        assert client.get("/api/v1/projects", headers=authorization).status_code == 200
        assert client.get("/api/v1/projects").status_code == 401
        revoke = client.delete(
            f"/api/v1/access/api-keys/{credential['id']}", headers=authorization
        )
        assert revoke.status_code == 200
        assert client.get("/api/v1/projects", headers=authorization).status_code == 401
    finally:
        monkeypatch.setenv("AUTH_MODE", "development")
        get_settings.cache_clear()

    async def seed_viewer() -> UUID:
        async with session_factory() as session:
            viewer = User(
                organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                email="viewer@pilot.invalid",
                display_name="Pilot Viewer",
                role="viewer",
                is_active=True,
            )
            session.add(viewer)
            await session.commit()
            return viewer.id

    viewer_id = asyncio.run(seed_viewer())
    viewer_headers = {"X-User-ID": str(viewer_id)}
    projects = client.get("/api/v1/projects", headers=viewer_headers)
    assert projects.status_code == 200
    assert any(item["id"] == project["id"] for item in projects.json())
    blocked = client.post(
        "/api/v1/projects", json={"name": "Blocked"}, headers=viewer_headers
    )
    assert blocked.status_code == 403


def test_pilot_feedback_and_admin_operations_are_tenant_scoped(m1_environment: Any) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Pilot acceptance"}).json()
    feedback = client.post(
        f"/api/v1/projects/{project['id']}/pilot-feedback",
        json={
            "category": "value",
            "severity": "low",
            "summary": "Useful evidence navigation",
            "details": (
                "The architect completed the evidence review faster than "
                "the manual baseline."
            ),
            "time_saved_minutes": 25,
        },
    )
    assert feedback.status_code == 201
    assert client.get(f"/api/v1/projects/{project['id']}/pilot-feedback").status_code == 200
    assert client.get("/api/v1/operations/overview").status_code == 403

    async def seed_admin() -> UUID:
        async with session_factory() as session:
            admin = User(
                organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                email="admin@pilot.invalid",
                display_name="Pilot Administrator",
                role="admin",
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            return admin.id

    admin_id = asyncio.run(seed_admin())
    admin_headers = {"X-User-ID": str(admin_id)}
    updated = client.patch(
        f"/api/v1/pilot-feedback/{feedback.json()['id']}",
        json={"status": "triaged"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    overview = client.get("/api/v1/operations/overview", headers=admin_headers)
    assert overview.status_code == 200
    assert overview.json()["pilot_feedback_by_status"] == {"triaged": 1}
    assert overview.json()["deterministic_checks_available"] is True
    assert client.get("/api/v1/operations/audit-events", headers=admin_headers).status_code == 200

    async def feedback_status() -> str:
        async with session_factory() as session:
            row = await session.scalar(select(PilotFeedback))
            assert row is not None
            return row.status

    assert asyncio.run(feedback_status()) == "triaged"


def test_job_runtime_is_idempotent_after_success(m1_environment: Any) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Idempotent worker"}).json()
    calls = 0

    async def arrange() -> UUID:
        async with session_factory() as session:
            job = Job(
                organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                project_id=UUID(project["id"]),
                job_type="test.idempotent",
                status="queued",
                progress=0,
                input_data={},
            )
            session.add(job)
            await session.commit()
            return job.id

    async def processor(_session: Any, _job: Job) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"completed": True}

    job_id = asyncio.run(arrange())
    asyncio.run(run_persisted_job(session_factory, job_id, processor, error_code="failed"))
    asyncio.run(run_persisted_job(session_factory, job_id, processor, error_code="failed"))
    assert calls == 1


def test_missing_information_is_an_actionable_project_scoped_list(
    m1_environment: Any,
) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Missing input pilot"}).json()
    run_id = uuid4()
    rule_id = uuid4()

    async def seed_run() -> None:
        async with session_factory() as session:
            package = ReviewPackage(
                project_id=UUID(project["id"]),
                name="Missing input review",
                status="completed",
                conflict_candidates=[],
                conflict_resolutions={},
            )
            session.add(package)
            await session.flush()
            run = CheckRun(
                id=run_id,
                review_package_id=package.id,
                status="completed",
                project_snapshot={"facts": []},
                rule_pack_snapshot=[
                    {
                        "rules": [
                            {
                                "id": str(rule_id),
                                "code": "EXIT-COUNT-001",
                                "inputs": [{"fact_key": "exit.count", "required": True}],
                            }
                        ]
                    }
                ],
                input_hash="a" * 64,
            )
            session.add(run)
            session.add(
                CheckResult(
                    check_run_id=run.id,
                    rule_id=rule_id,
                    status="insufficient_information",
                    severity="critical",
                    message="Required fact is missing",
                    fact_ids=[],
                    regulation_evidence_ids=[],
                    project_evidence_ids=[],
                    trace={},
                )
            )
            await session.commit()

    asyncio.run(seed_run())
    response = client.get(f"/api/v1/check-runs/{run_id}/missing-information")
    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "fact_key": "exit.count",
            "affected_rules": ["EXIT-COUNT-001"],
            "severity": "critical",
            "action": "Provide and verify project evidence for 'exit.count'.",
        }
    ]


def test_model_guard_limits_times_out_and_leaves_deterministic_path_available() -> None:
    async def value() -> str:
        return "ok"

    disabled = ModelCallGuard(enabled=False, timeout_seconds=1, requests_per_minute=1)
    with pytest.raises(ExternalModelUnavailable):
        asyncio.run(disabled.run(value))

    limited = ModelCallGuard(enabled=True, timeout_seconds=1, requests_per_minute=1)
    assert asyncio.run(limited.run(value)) == "ok"
    with pytest.raises(ExternalModelRateLimited):
        asyncio.run(limited.run(value))

    async def slow() -> str:
        await asyncio.sleep(0.02)
        return "late"

    timeout = ModelCallGuard(enabled=True, timeout_seconds=0.001, requests_per_minute=10)
    with pytest.raises(TimeoutError):
        asyncio.run(timeout.run(slow))


def test_deterministic_rule_throughput_is_suitable_for_pilot() -> None:
    from time import perf_counter

    from app.domain.enums import CheckStatus
    from app.services.rule_engine import evaluate_rule

    started = perf_counter()
    statuses = [
        evaluate_rule(
            title="Exit count",
            applicability={},
            expression={"op": "gte", "fact": "exit.count", "value": 2},
            inputs=[{"fact_key": "exit.count"}],
            missing_data_status="insufficient_information",
            facts={"exit.count": {"value": 1}},
        ).status
        for _ in range(5000)
    ]
    elapsed = perf_counter() - started
    assert set(statuses) == {CheckStatus.NON_COMPLIANT}
    assert elapsed < 2
