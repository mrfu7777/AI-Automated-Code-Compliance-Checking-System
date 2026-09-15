import asyncio
from typing import Any
from uuid import UUID

from app.db.models import Clause, Evidence, FileVersion, ProjectFact, Standard, StandardVersion
from app.services.job_runtime import run_persisted_job
from app.services.review_impact import (
    affected_rule_ids,
    changed_fact_keys,
    conflict_candidates,
    dependency_graph,
)
from app.tasks.check_processing import execute_check


async def _seed_published_clause(
    session_factory: Any, organization_id: UUID
) -> Clause:
    async with session_factory() as session:
        source = FileVersion(
            project_file_id=None,
            version_number=1,
            original_filename="m6-code.pdf",
            media_type="application/pdf",
            size_bytes=10,
            sha256="a" * 64,
            object_key="tests/m6-code.pdf",
        )
        standard = Standard(
            organization_id=organization_id,
            code="GB-M6-TEST",
            title="M6 test fire code",
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


def test_dependency_impact_and_conflicts_are_deterministic() -> None:
    packs = [
        {
            "id": "pack-national",
            "authority_level": "national",
            "rules": [
                {
                    "id": "rule-a",
                    "code": "A",
                    "inputs": [{"fact_key": "exit.count"}],
                    "applicability": {"op": "eq", "fact": "building.use", "value": "office"},
                    "expression": {"op": "eq", "fact": "exit.count", "value": 2},
                }
            ],
        },
        {
            "id": "pack-local",
            "authority_level": "local",
            "rules": [
                {
                    "id": "rule-b",
                    "code": "B",
                    "inputs": [{"fact_key": "exit.count"}],
                    "applicability": {},
                    "expression": {"op": "eq", "fact": "exit.count", "value": 3},
                }
            ],
        },
    ]
    before = {
        "facts": [{"key": "exit.count", "value": 2, "unit": "count", "scope_data": {}}]
    }
    after = {
        "facts": [{"key": "exit.count", "value": 3, "unit": "count", "scope_data": {}}]
    }
    assert changed_fact_keys(before, after) == ["exit.count"]
    assert affected_rule_ids(packs, ["building.use"]) == ["rule-a"]
    graph = dependency_graph(packs)
    assert {edge["target"] for edge in graph["edges"]} == {"rule:rule-a", "rule:rule-b"}
    conflicts = conflict_candidates(packs)
    assert conflicts[0]["rule_ids"] == ["rule-a", "rule-b"]
    assert conflicts[0]["authority_levels"] == ["national", "local"]


def test_incremental_run_rechecks_only_dependent_rules(m1_environment: Any) -> None:
    client, _storage, dispatcher, session_factory = m1_environment
    project = client.post(
        "/api/v1/projects",
        json={
            "name": "M6 pilot",
            "jurisdiction": "CN",
            "design_date": "2026-09-15",
            "building_type": "office",
        },
    ).json()
    clause = asyncio.run(
        _seed_published_clause(
            session_factory, UUID("00000000-0000-0000-0000-000000000001")
        )
    )
    pack = client.post(
        "/api/v1/rule-packs",
        json={
            "standard_version_id": str(clause.standard_version_id),
            "name": "Incremental rules",
            "semantic_version": "1.0.0",
            "authority_level": "national",
        },
    ).json()
    rule_ids = []
    for code, key, threshold in (
        ("EXIT", "exit.count", 2),
        ("STAIR", "stair.count", 2),
    ):
        rule = client.post(
            f"/api/v1/rule-packs/{pack['id']}/rules",
            json={
                "source_clause_id": str(clause.id),
                "code": code,
                "title": code,
                "severity": "critical",
                "inputs": [{"fact_key": key, "required": True, "expected_unit": "count"}],
                "applicability": {},
                "expression": {
                    "op": "eq" if code == "EXIT" else "gte",
                    "fact": key,
                    "value": threshold,
                    "unit": "count",
                },
            },
        ).json()
        rule_ids.append(rule["id"])
        assert client.post(f"/api/v1/rules/{rule['id']}/review").status_code == 200
    assert client.post(f"/api/v1/rule-packs/{pack['id']}/publish").status_code == 200
    for key in ("exit.count", "stair.count"):
        assert (
            client.post(
                f"/api/v1/projects/{project['id']}/facts",
                json={"key": key, "value": 2, "unit": "count", "justification": "Seed"},
            ).status_code
            == 201
        )
    created = client.post(
        "/api/v1/check-runs",
        json={"project_id": project["id"], "rule_pack_ids": [pack["id"]]},
    ).json()
    baseline_job_id = dispatcher.dispatched[-1][0]
    asyncio.run(
        run_persisted_job(
            session_factory, baseline_job_id, execute_check, error_code="check_run_failed"
        )
    )
    baseline_id = created["run"]["id"]
    client.post(
        f"/api/v1/projects/{project['id']}/facts",
        json={
            "key": "exit.count",
            "value": 1,
            "unit": "count",
            "justification": "Changed drawing",
        },
    )
    impact = client.get(f"/api/v1/check-runs/{baseline_id}/impact").json()
    assert impact["changed_fact_keys"] == ["exit.count"]
    assert len(impact["affected_rule_ids"]) == 1
    incremental = client.post(
        "/api/v1/check-runs/incremental",
        json={"baseline_run_id": baseline_id},
    )
    assert incremental.status_code == 201
    body = incremental.json()
    assert body["run"]["run_mode"] == "incremental"
    incremental_job_id = dispatcher.dispatched[-1][0]
    asyncio.run(
        run_persisted_job(
            session_factory, incremental_job_id, execute_check, error_code="check_run_failed"
        )
    )
    completed = client.get(f"/api/v1/check-runs/{body['run']['id']}").json()
    traces = {item["rule_id"]: item["trace"]["incremental"] for item in completed["results"]}
    assert sum(item["executed"] for item in traces.values()) == 1
    comparison = client.get(
        f"/api/v1/check-runs/{completed['id']}/compare/{baseline_id}"
    ).json()
    assert comparison["summary"]["regressed"] == 1
    comparison_report = client.get(
        f"/api/v1/check-runs/{completed['id']}/comparison-report/{baseline_id}"
    )
    assert comparison_report.status_code == 200
    assert "attachment" in comparison_report.headers["content-disposition"]
    graph = client.get(
        f"/api/v1/review-packages/{completed['review_package_id']}/dependency-graph"
    )
    assert graph.status_code == 200
    assert len(graph.json()["edges"]) == 2
    suggestions = client.get(
        f"/api/v1/projects/{project['id']}/standard-version-recommendations"
    )
    assert suggestions.status_code == 200
    assert suggestions.json()[0]["recommended"] is True

    local_pack = client.post(
        "/api/v1/rule-packs",
        json={
            "standard_version_id": str(clause.standard_version_id),
            "name": "Local rules",
            "semantic_version": "2.0.0",
            "authority_level": "local",
        },
    ).json()
    local_rule = client.post(
        f"/api/v1/rule-packs/{local_pack['id']}/rules",
        json={
            "source_clause_id": str(clause.id),
            "code": "LOCAL-EXIT",
            "title": "Local exit count",
            "severity": "critical",
            "inputs": [{"fact_key": "exit.count", "required": True}],
            "applicability": {},
            "expression": {"op": "eq", "fact": "exit.count", "value": 3},
        },
    ).json()
    client.post(f"/api/v1/rules/{local_rule['id']}/review")
    client.post(f"/api/v1/rule-packs/{local_pack['id']}/publish")
    multi_created = client.post(
        "/api/v1/check-runs",
        json={"project_id": project["id"], "rule_pack_ids": [pack["id"], local_pack["id"]]},
    ).json()
    multi_job_id = dispatcher.dispatched[-1][0]
    asyncio.run(
        run_persisted_job(
            session_factory, multi_job_id, execute_check, error_code="check_run_failed"
        )
    )
    multi_run = client.get(f"/api/v1/check-runs/{multi_created['run']['id']}").json()
    conflict_results = [
        item for item in multi_run["results"] if item["status"] == "manual_review_required"
    ]
    assert len(conflict_results) == 2
    conflicts = client.get(
        f"/api/v1/review-packages/{multi_run['review_package_id']}/conflicts"
    ).json()
    assert len(conflicts) == 1
    conflict_id = conflicts[0]["id"]
    invalid_resolution = client.put(
        f"/api/v1/review-packages/{multi_run['review_package_id']}/conflicts/{conflict_id}",
        json={
            "selected_rule_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "note": "Invalid",
        },
    )
    assert invalid_resolution.status_code == 422
    resolution = client.put(
        f"/api/v1/review-packages/{multi_run['review_package_id']}/conflicts/{conflict_id}",
        json={"selected_rule_id": rule_ids[0], "note": "Architect decision"},
    )
    assert resolution.status_code == 200
    assert resolution.json()["resolution"]["selected_rule_id"] == rule_ids[0]
    resolved_incremental = client.post(
        "/api/v1/check-runs/incremental",
        json={"baseline_run_id": multi_run["id"], "name": "Conflict resolved"},
    ).json()
    resolved_job_id = dispatcher.dispatched[-1][0]
    asyncio.run(
        run_persisted_job(
            session_factory, resolved_job_id, execute_check, error_code="check_run_failed"
        )
    )
    resolved = client.get(
        f"/api/v1/check-runs/{resolved_incremental['run']['id']}"
    ).json()
    statuses = {item["rule_id"]: item["status"] for item in resolved["results"]}
    assert statuses[local_rule["id"]] == "not_applicable"
    assert statuses[rule_ids[0]] == "non_compliant"


def test_replacement_file_invalidates_evidence_fact(m1_environment: Any) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "Versioned drawings"}).json()
    first = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "A-101"},
        files={"upload": ("a101.pdf", b"%PDF-1.7\nfirst", "application/pdf")},
    ).json()

    async def seed_fact() -> UUID:
        async with session_factory() as session:
            fact = ProjectFact(
                project_id=UUID(project["id"]),
                key="exit.count",
                value=2,
                unit="count",
                scope_data={},
                source="drawing",
                verification_status="verified",
            )
            session.add(fact)
            await session.flush()
            session.add(
                Evidence(
                    organization_id=UUID("00000000-0000-0000-0000-000000000001"),
                    project_fact_id=fact.id,
                    file_version_id=UUID(first["file_version"]["id"]),
                    kind="image_region",
                    location={"page": 1},
                )
            )
            await session.commit()
            return fact.id

    fact_id = asyncio.run(seed_fact())
    second = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "A-101"},
        files={"upload": ("a101-revised.pdf", b"%PDF-1.7\nsecond", "application/pdf")},
    )
    assert second.status_code == 201

    async def fact_status() -> str:
        async with session_factory() as session:
            return (await session.get_one(ProjectFact, fact_id)).verification_status

    assert asyncio.run(fact_status()) == "stale"


def test_standard_edition_comparison_uses_clause_numbers(m1_environment: Any) -> None:
    client, _storage, _dispatcher, session_factory = m1_environment
    organization_id = UUID("00000000-0000-0000-0000-000000000001")
    first_clause = asyncio.run(_seed_published_clause(session_factory, organization_id))

    async def seed_new_edition() -> UUID:
        async with session_factory() as session:
            old_version = await session.get_one(StandardVersion, first_clause.standard_version_id)
            source = FileVersion(
                project_file_id=None,
                version_number=2,
                original_filename="code-2027.pdf",
                media_type="application/pdf",
                size_bytes=10,
                sha256="b" * 64,
                object_key="tests/m6-code-2027.pdf",
            )
            session.add(source)
            await session.flush()
            version = StandardVersion(
                standard_id=old_version.standard_id,
                edition="2027",
                lifecycle_status="published",
                source_file_version_id=source.id,
                document_hash=source.sha256,
                supersedes_id=old_version.id,
            )
            session.add(version)
            await session.flush()
            session.add_all(
                [
                    Clause(
                        standard_version_id=version.id,
                        clause_number="6.4.1",
                        level="article",
                        original_text="The revised clear width requirement.",
                        page_number=13,
                        order_index=1,
                        lifecycle_status="published",
                    ),
                    Clause(
                        standard_version_id=version.id,
                        clause_number="6.4.2",
                        level="article",
                        original_text="A newly introduced requirement.",
                        page_number=13,
                        order_index=2,
                        lifecycle_status="published",
                    ),
                ]
            )
            await session.commit()
            return version.id

    second_version_id = asyncio.run(seed_new_edition())
    comparison = client.get(
        f"/api/v1/regulations/versions/{first_clause.standard_version_id}/compare/{second_version_id}"
    )
    assert comparison.status_code == 200
    assert comparison.json()["summary"] == {"modified": 1, "added": 1}
