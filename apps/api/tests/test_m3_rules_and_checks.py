import asyncio
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.dependencies import _ensure_default_actor
from app.db.models import Clause, Evidence, FileVersion, Job, Standard, StandardVersion
from app.domain.enums import CheckStatus
from app.services.dispatch import CeleryJobDispatcher, get_job_dispatcher
from app.services.job_runtime import run_persisted_job
from app.services.rule_engine import RuleValidationError, evaluate_rule, validate_expression
from app.services.rule_templates import RULE_TEMPLATES
from app.tasks.check_processing import execute_check


def _fact_for(expression: dict[str, Any], mode: str) -> dict[str, dict[str, Any]]:
    operator = expression["op"]
    expected = expression["value"]
    if operator == "gte":
        value = expected if mode == "boundary" else expected + (1 if mode == "pass" else -1)
    elif operator == "lte":
        value = expected if mode == "boundary" else expected - (1 if mode == "pass" else -1)
    elif operator == "eq":
        value = expected if mode != "fail" else not expected
    else:
        value = expected[0] if mode != "fail" else "not-allowed"
    return {expression["fact"]: {"value": value, "unit": expression.get("unit")}}


@pytest.mark.parametrize("template", RULE_TEMPLATES, ids=lambda item: item.key)
def test_golden_rule_templates_cover_pass_fail_missing_and_boundary(template: Any) -> None:
    for mode, expected_status in (
        ("pass", CheckStatus.COMPLIANT),
        ("fail", CheckStatus.NON_COMPLIANT),
        ("boundary", CheckStatus.COMPLIANT),
    ):
        result = evaluate_rule(
            title=template.title,
            applicability=template.applicability,
            expression=template.expression,
            inputs=template.inputs,
            missing_data_status="insufficient_information",
            facts=_fact_for(template.expression, mode),
        )
        assert result.status == expected_status
    missing = evaluate_rule(
        title=template.title,
        applicability=template.applicability,
        expression=template.expression,
        inputs=template.inputs,
        missing_data_status="insufficient_information",
        facts={},
    )
    assert missing.status == CheckStatus.INSUFFICIENT_INFORMATION


def test_rule_engine_handles_applicability_units_and_restricted_operators() -> None:
    not_applicable = evaluate_rule(
        title="Width",
        applicability={"op": "eq", "fact": "building.use", "value": "office"},
        expression={"op": "gte", "fact": "width", "value": 1.1, "unit": "m"},
        inputs=[{"fact_key": "building.use"}, {"fact_key": "width"}],
        missing_data_status="insufficient_information",
        facts={
            "building.use": {"value": "warehouse", "unit": None},
            "width": {"value": 110, "unit": "cm"},
        },
    )
    assert not_applicable.status == CheckStatus.NOT_APPLICABLE
    converted = evaluate_rule(
        title="Width",
        applicability={},
        expression={"op": "gte", "fact": "width", "value": 1.1, "unit": "m"},
        inputs=[{"fact_key": "width"}],
        missing_data_status="insufficient_information",
        facts={"width": {"value": 110, "unit": "cm"}},
    )
    assert converted.status == CheckStatus.COMPLIANT
    with pytest.raises(RuleValidationError):
        validate_expression({"op": "python", "value": "dangerous"})


def test_rule_engine_composites_and_conversion_failures_are_safe() -> None:
    composite = evaluate_rule(
        title="Composite",
        applicability={},
        expression={
            "op": "all",
            "conditions": [
                {"op": "ne", "fact": "kind", "value": "shed"},
                {
                    "op": "any",
                    "conditions": [
                        {"op": "gt", "fact": "height", "value": 10},
                        {"op": "not", "condition": {"op": "eq", "fact": "open", "value": False}},
                    ],
                },
            ],
        },
        inputs=[{"fact_key": "kind"}, {"fact_key": "height"}, {"fact_key": "open"}],
        missing_data_status="manual_review_required",
        facts={
            "kind": {"value": "office"},
            "height": {"value": 11},
            "open": {"value": True},
        },
    )
    assert composite.status == CheckStatus.COMPLIANT
    conversion = evaluate_rule(
        title="Bad unit",
        applicability={},
        expression={"op": "gte", "fact": "area", "value": 2, "unit": "m2"},
        inputs=[{"fact_key": "area"}],
        missing_data_status="insufficient_information",
        facts={"area": {"value": 2, "unit": "m"}},
    )
    assert conversion.status == CheckStatus.MANUAL_REVIEW_REQUIRED
    with pytest.raises(RuleValidationError):
        validate_expression({"op": "all", "conditions": []})
    with pytest.raises(RuleValidationError):
        validate_expression({"op": "not", "condition": "invalid"})
    with pytest.raises(RuleValidationError):
        validate_expression({"op": "eq", "value": 1})
    with pytest.raises(RuleValidationError):
        validate_expression({"op": "all", "conditions": ["invalid"]})
    no_unit = evaluate_rule(
        title="No unit",
        applicability={},
        expression={"op": "lt", "fact": "length", "value": 2, "unit": "m"},
        inputs=[{"fact_key": "length"}],
        missing_data_status="insufficient_information",
        facts={"length": {"value": 100}},
    )
    assert no_unit.status == CheckStatus.MANUAL_REVIEW_REQUIRED
    non_numeric = evaluate_rule(
        title="Bad numeric fact",
        applicability={},
        expression={"op": "lte", "fact": "length", "value": 2, "unit": "m"},
        inputs=[{"fact_key": "length"}],
        missing_data_status="insufficient_information",
        facts={"length": {"value": "one hundred", "unit": "cm"}},
    )
    assert non_numeric.status == CheckStatus.MANUAL_REVIEW_REQUIRED
    applicability_missing = evaluate_rule(
        title="Scoped",
        applicability={"op": "eq", "fact": "scope", "value": "tower"},
        expression={"op": "eq", "fact": "provided", "value": True},
        inputs=[{"fact_key": "provided"}],
        missing_data_status="insufficient_information",
        facts={"provided": {"value": True}},
    )
    assert applicability_missing.status == CheckStatus.INSUFFICIENT_INFORMATION
    with pytest.raises(RuleValidationError, match="Invalid operands"):
        evaluate_rule(
            title="Invalid operands",
            applicability={},
            expression={"op": "in", "fact": "rating", "value": 3},
            inputs=[{"fact_key": "rating"}],
            missing_data_status="insufficient_information",
            facts={"rating": {"value": "I"}},
        )


def test_generic_dispatcher_routes_every_persisted_job_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.tasks.check_processing import process_check_run
    from app.tasks.file_processing import process_file_version
    from app.tasks.regulation_processing import process_regulation

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(process_file_version, "delay", lambda value: calls.append(("file", value)))
    monkeypatch.setattr(
        process_regulation, "delay", lambda value: calls.append(("regulation", value))
    )
    monkeypatch.setattr(process_check_run, "delay", lambda value: calls.append(("check", value)))
    dispatcher = CeleryJobDispatcher()
    job_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    dispatcher.dispatch(job_id, "file.metadata")
    dispatcher.dispatch(job_id, "regulation.parse")
    dispatcher.dispatch(job_id, "check.run")
    assert [item[0] for item in calls] == ["file", "regulation", "check"]
    assert isinstance(get_job_dispatcher(), CeleryJobDispatcher)
    with pytest.raises(ValueError, match="Unsupported job type"):
        dispatcher.dispatch(job_id, "unknown")


def test_job_runtime_records_processor_failure(m1_environment: Any) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Failed check"}).json()

    async def arrange_and_run() -> Job:
        async with session_factory() as session:
            job = Job(
                organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                project_id=UUID(project["id"]),
                job_type="check.run",
                status="queued",
                progress=0,
                input_data={"check_run_id": "missing"},
            )
            session.add(job)
            await session.commit()
            job_id = job.id

        async def fail(_session: Any, _job: Job) -> dict[str, Any]:
            raise RuntimeError("deterministic failure")

        with pytest.raises(RuntimeError, match="deterministic failure"):
            await run_persisted_job(session_factory, job_id, fail, error_code="expected_failure")
        async with session_factory() as session:
            return await session.scalar(select(Job).where(Job.id == job_id))  # type: ignore[return-value]

    failed = asyncio.run(arrange_and_run())
    assert failed.status == "failed"
    assert failed.error_data == {"code": "expected_failure", "message": "deterministic failure"}


def test_job_runtime_rejects_missing_job(m1_environment: Any) -> None:
    _client, _storage, _dispatcher, session_factory = m1_environment

    async def unused(_session: Any, _job: Job) -> dict[str, Any]:
        return {}

    with pytest.raises(ValueError, match="does not exist"):
        asyncio.run(
            run_persisted_job(
                session_factory,
                UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
                unused,
                error_code="unused",
            )
        )


def test_default_actor_bootstrap_is_idempotent(m1_environment: Any) -> None:
    _client, _storage, _dispatcher, session_factory = m1_environment

    async def bootstrap_twice() -> tuple[UUID, UUID]:
        async with session_factory() as session:
            first = await _ensure_default_actor(session)
            second = await _ensure_default_actor(session)
            return first.id, second.id

    first_id, second_id = asyncio.run(bootstrap_twice())
    assert first_id == second_id


async def _seed_published_clause(
    session_factory: async_sessionmaker, organization_id: UUID
) -> Clause:
    async with session_factory() as session:
        source = FileVersion(
            project_file_id=None,
            version_number=1,
            original_filename="code.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            object_key="tests/m3-code.pdf",
        )
        standard = Standard(
            organization_id=organization_id,
            code="GB-TEST",
            title="Test fire code",
            jurisdiction="CN",
        )
        session.add_all([source, standard])
        await session.flush()
        version = StandardVersion(
            standard_id=standard.id,
            edition="2026",
            lifecycle_status="published",
            source_file_version_id=source.id,
            document_hash=source.sha256,
        )
        session.add(version)
        await session.flush()
        clause = Clause(
            standard_version_id=version.id,
            clause_number="6.4.1",
            level="article",
            original_text="The clear width shall meet the reviewed requirement.",
            page_number=12,
            order_index=1,
            lifecycle_status="published",
        )
        session.add(clause)
        await session.flush()
        session.add(
            Evidence(
                organization_id=organization_id,
                clause_id=clause.id,
                file_version_id=source.id,
                kind="document_region",
                location={"page": 12},
                excerpt=clause.original_text,
            )
        )
        await session.commit()
        return clause


def test_m3_review_flow_is_versioned_traceable_and_snapshot_safe(m1_environment: Any) -> None:
    client, _storage, dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "M3 pilot"}).json()
    clauses = asyncio.run(
        _seed_published_clause(session_factory, UUID("00000000-0000-0000-0000-000000000001"))
    )

    pack_response = client.post(
        "/api/v1/rule-packs",
        json={
            "standard_version_id": str(clauses.standard_version_id),
            "name": "Pilot rules",
            "semantic_version": "1.0.0",
        },
    )
    assert pack_response.status_code == 201
    pack = pack_response.json()
    assert (
        client.post(
            "/api/v1/rule-packs",
            json={
                "standard_version_id": str(clauses.standard_version_id),
                "name": "Duplicate",
                "semantic_version": "1.0.0",
            },
        ).status_code
        == 409
    )
    assert client.get("/api/v1/rule-templates").status_code == 200
    assert client.get("/api/v1/rule-packs").json()[0]["id"] == pack["id"]
    rule_response = client.post(
        f"/api/v1/rule-packs/{pack['id']}/rules",
        json={
            "source_clause_id": str(clauses.id),
            "code": "EGRESS-WIDTH-001",
            "title": "Egress width",
            "severity": "critical",
            "inputs": [{"fact_key": "egress.width", "required": True, "expected_unit": "m"}],
            "applicability": {},
            "expression": {"op": "gte", "fact": "egress.width", "value": 1.1, "unit": "m"},
            "missing_data_status": "insufficient_information",
        },
    )
    assert rule_response.status_code == 201
    rule = rule_response.json()
    invalid_rule = {
        "source_clause_id": str(clauses.id),
        "code": "INVALID",
        "title": "Invalid",
        "severity": "high",
        "inputs": [],
        "applicability": {},
        "expression": {"op": "eval", "fact": "x", "value": 1},
    }
    assert (
        client.post(f"/api/v1/rule-packs/{pack['id']}/rules", json=invalid_rule).status_code == 422
    )
    duplicate_rule = {
        "source_clause_id": str(clauses.id),
        "code": "EGRESS-WIDTH-001",
        "title": "Duplicate",
        "severity": "high",
        "inputs": [],
        "applicability": {},
        "expression": {"op": "eq", "fact": "x", "value": 1},
    }
    assert (
        client.post(f"/api/v1/rule-packs/{pack['id']}/rules", json=duplicate_rule).status_code
        == 409
    )
    assert client.get(f"/api/v1/rule-packs/{pack['id']}/rules").json()[0]["id"] == rule["id"]
    assert client.post(f"/api/v1/rule-packs/{pack['id']}/publish").status_code == 409
    trial = client.post(
        f"/api/v1/rules/{rule['id']}/trial",
        json={"facts": {"egress.width": {"value": 110, "unit": "cm"}}},
    ).json()
    assert trial["status"] == "compliant"
    assert trial["clause"]["evidence_ids"]
    assert client.post(f"/api/v1/rules/{rule['id']}/review").status_code == 200
    updated = client.patch(f"/api/v1/rules/{rule['id']}", json={"title": "Reviewed egress width"})
    assert updated.json()["lifecycle_status"] == "draft"
    assert client.post(f"/api/v1/rules/{rule['id']}/review").status_code == 200
    published = client.post(f"/api/v1/rule-packs/{pack['id']}/publish")
    assert published.status_code == 200
    assert len(published.json()["content_hash"]) == 64
    assert client.post(f"/api/v1/rule-packs/{pack['id']}/publish").status_code == 200
    assert client.patch(f"/api/v1/rules/{rule['id']}", json={"title": "Changed"}).status_code == 409
    clone_response = client.post(
        f"/api/v1/rule-packs/{pack['id']}/clone", json={"semantic_version": "1.1.0"}
    )
    assert clone_response.status_code == 201
    cloned = clone_response.json()
    assert (
        client.post(
            f"/api/v1/rule-packs/{pack['id']}/clone", json={"semantic_version": "1.1.0"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/rule-packs/{cloned['id']}/clone", json={"semantic_version": "2.0.0"}
        ).status_code
        == 409
    )

    fact_one = client.post(
        f"/api/v1/projects/{project['id']}/facts",
        json={
            "key": "egress.width",
            "value": 100,
            "unit": "cm",
            "justification": "Measured on A-101",
        },
    )
    assert fact_one.status_code == 201
    run_response = client.post(
        "/api/v1/check-runs",
        json={"project_id": project["id"], "rule_pack_ids": [pack["id"]], "name": "First review"},
    )
    assert run_response.status_code == 201
    run = run_response.json()["run"]
    job_id, job_type = dispatcher.dispatched[-1]
    assert job_type == "check.run"
    asyncio.run(
        run_persisted_job(session_factory, job_id, execute_check, error_code="check_run_failed")
    )
    completed = client.get(f"/api/v1/check-runs/{run['id']}").json()
    assert completed["results"][0]["status"] == "non_compliant"
    assert completed["results"][0]["regulation_evidence_ids"]
    assert completed["results"][0]["project_evidence_ids"]
    assert completed["results"][0]["trace"]["clause"]["original_text"]

    fact_two = client.post(
        f"/api/v1/projects/{project['id']}/facts",
        json={
            "key": "egress.width",
            "value": 120,
            "unit": "cm",
            "justification": "Verified remeasure",
        },
    ).json()
    assert fact_two["supersedes_id"] == fact_one.json()["id"]
    assert len(client.get(f"/api/v1/projects/{project['id']}/facts").json()) == 1
    assert (
        len(client.get(f"/api/v1/projects/{project['id']}/facts?include_history=true").json()) == 2
    )
    assert client.get(f"/api/v1/check-runs/{run['id']}").json()["input_hash"] == run["input_hash"]
    second_response = client.post(
        "/api/v1/check-runs",
        json={"project_id": project["id"], "rule_pack_ids": [pack["id"]], "name": "Second review"},
    ).json()
    second_job_id = dispatcher.dispatched[-1][0]
    asyncio.run(
        run_persisted_job(
            session_factory,
            second_job_id,
            execute_check,
            error_code="check_run_failed",
        )
    )
    second = client.get(f"/api/v1/check-runs/{second_response['run']['id']}").json()
    assert second["results"][0]["status"] == "compliant"
    assert completed["input_hash"] != second["input_hash"]
    assert len(client.get(f"/api/v1/projects/{project['id']}/check-runs").json()) == 2
    export = client.get(f"/api/v1/check-runs/{run['id']}/export")
    assert export.status_code == 200
    assert "attachment" in export.headers["content-disposition"]


def test_m3_rejects_unowned_or_unpublished_inputs(m1_environment: Any) -> None:
    client, _storage, _dispatcher, _session_factory = m1_environment
    missing = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert client.get(f"/api/v1/rule-packs/{missing}/rules").status_code == 404
    assert client.patch(f"/api/v1/rules/{missing}", json={"title": "Missing"}).status_code == 404
    assert client.post(f"/api/v1/rules/{missing}/review").status_code == 404
    assert client.post(f"/api/v1/rules/{missing}/trial", json={"facts": {}}).status_code == 404
    assert client.get(f"/api/v1/check-runs/{missing}").status_code == 404
    assert client.get(f"/api/v1/projects/{missing}/facts").status_code == 404
    assert (
        client.post(
            "/api/v1/rule-packs",
            json={"standard_version_id": missing, "name": "Missing", "semantic_version": "1.0.0"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/check-runs",
            json={"project_id": missing, "rule_pack_ids": [missing]},
        ).status_code
        == 404
    )
    project = client.post("/api/v1/projects", json={"name": "No pack"}).json()
    assert (
        client.post(
            "/api/v1/check-runs",
            json={"project_id": project["id"], "rule_pack_ids": [missing]},
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/projects/{missing}/check-runs").status_code == 404
    assert client.get(f"/api/v1/check-runs/{missing}/export").status_code == 404
