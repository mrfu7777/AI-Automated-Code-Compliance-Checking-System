from app.db import models  # noqa: F401
from app.db.base import Base


def test_core_domain_tables_are_registered() -> None:
    expected_tables = {
        "organizations",
        "users",
        "projects",
        "project_files",
        "file_versions",
        "standards",
        "standard_versions",
        "clauses",
        "clause_revisions",
        "document_pages",
        "rule_packs",
        "rules",
        "project_facts",
        "evidence",
        "review_packages",
        "review_package_rule_packs",
        "check_runs",
        "check_results",
        "jobs",
        "audit_events",
    }

    assert expected_tables == set(Base.metadata.tables)
