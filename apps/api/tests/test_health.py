from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "code-compliance-api",
        "api_version": "v1",
    }
    assert response.headers["X-Request-ID"] == "test-request"


def test_contract_endpoint_exposes_non_ambiguous_check_states() -> None:
    response = client.get("/api/v1/contracts")

    assert response.status_code == 200
    assert response.json()["check_statuses"] == [
        "compliant",
        "non_compliant",
        "insufficient_information",
        "manual_review_required",
        "not_applicable",
    ]
