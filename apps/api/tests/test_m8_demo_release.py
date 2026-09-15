import asyncio
from typing import Any

import pytest

from app.core.config import get_settings
from app.services.job_runtime import run_persisted_job
from app.tasks.check_processing import execute_check


def test_demo_endpoint_is_disabled_unless_explicitly_enabled(m1_environment: Any) -> None:
    client, _storage, _dispatcher, _session_factory = m1_environment
    assert client.post("/api/v1/demo/scenario").status_code == 404


def test_synthetic_demo_runs_through_the_existing_review_chain(
    m1_environment: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, storage, dispatcher, session_factory = m1_environment
    monkeypatch.setenv("DEMO_MODE_ENABLED", "true")
    get_settings.cache_clear()
    try:
        seeded = client.post("/api/v1/demo/scenario")
        assert seeded.status_code == 201
        scenario = seeded.json()
        assert scenario["created"] is True
        assert scenario["project_name"].startswith("[DEMO]")
        assert len(storage.objects) == 4

        project_id = scenario["project_id"]
        pack_id = scenario["rule_pack_id"]
        assert len(client.get(f"/api/v1/projects/{project_id}/files").json()) == 2
        assert len(client.get(f"/api/v1/projects/{project_id}/facts").json()) == 3
        rules = client.get(f"/api/v1/rule-packs/{pack_id}/rules").json()
        assert len(rules) == 4

        created = client.post(
            "/api/v1/check-runs",
            json={
                "project_id": project_id,
                "rule_pack_ids": [pack_id],
                "name": "V1 guided demonstration",
            },
        )
        assert created.status_code == 201
        job_id, job_type = dispatcher.dispatched[-1]
        assert job_type == "check.run"
        asyncio.run(
            run_persisted_job(
                session_factory,
                job_id,
                execute_check,
                error_code="check_run_failed",
            )
        )
        run_id = created.json()["run"]["id"]
        completed = client.get(f"/api/v1/check-runs/{run_id}").json()
        codes = {item["id"]: item["code"] for item in rules}
        actual = {codes[item["rule_id"]]: item["status"] for item in completed["results"]}
        assert actual == scenario["expected_statuses"]
        for result in completed["results"]:
            assert result["regulation_evidence_ids"]
            if result["status"] in {"compliant", "non_compliant"}:
                assert result["project_evidence_ids"]

        workbench = client.get(f"/api/v1/check-runs/{run_id}/workbench").json()
        assert len(workbench["findings"]) == 4
        assert all(item["regulation_evidence"][0]["image_url"] for item in workbench["findings"])
        missing = client.get(f"/api/v1/check-runs/{run_id}/missing-information").json()
        assert [item["fact_key"] for item in missing["items"]] == [
            "fire_compartment.area_m2"
        ]
        assert client.get(f"/api/v1/check-runs/{run_id}/reports/pdf").status_code == 200
        assert client.get(f"/api/v1/check-runs/{run_id}/reports/xlsx").status_code == 200

        repeated = client.post("/api/v1/demo/scenario").json()
        assert repeated["created"] is False
        assert repeated["project_id"] == project_id
        assert repeated["rule_pack_id"] == pack_id
        assert len(storage.objects) == 4

        manifest = client.get("/api/v1/release").json()
        assert manifest["app_version"] == "1.0.0"
        assert manifest["schema_revision"] == "c73f20e184ad"
        assert manifest["demo_mode_enabled"] is True
    finally:
        monkeypatch.setenv("DEMO_MODE_ENABLED", "false")
        get_settings.cache_clear()
