from fastapi.testclient import TestClient

from app import create_app
from control_plane.runtime import AgentRuntime


def payload(*, risk: str = "low", evidence: list[str] | None = None) -> dict:
    return {
        "goal": "resolve customer request",
        "observation": {"ticket_id": "T-100"},
        "contract": {
            "version": "support-v1",
            "allowed_action_ids": ["reply"],
            "granted_permissions": [],
        },
        "candidates": [
            {
                "action_id": "reply",
                "name": "Reply to customer",
                "tool": "support_api",
                "operation": "reply",
                "expected_value": 0.8,
                "risk": risk,
                "evidence": evidence or [],
            }
        ],
    }


def test_health() -> None:
    client = TestClient(create_app(AgentRuntime()))
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.2.0"}


def test_create_and_get_run() -> None:
    client = TestClient(create_app(AgentRuntime()))
    created = client.post("/v1/runs", json=payload())

    assert created.status_code == 201
    run_id = created.json()["run_id"]
    fetched = client.get(f"/v1/runs/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run_id


def test_validation_error_for_duplicate_action_ids() -> None:
    client = TestClient(create_app(AgentRuntime()))
    body = payload()
    body["candidates"].append(body["candidates"][0].copy())

    response = client.post("/v1/runs", json=body)
    assert response.status_code == 422


def test_unknown_run_returns_404() -> None:
    client = TestClient(create_app(AgentRuntime()))
    response = client.get("/v1/runs/missing")
    assert response.status_code == 404


def test_decision_endpoint_approves_waiting_run() -> None:
    client = TestClient(create_app(AgentRuntime()))
    created = client.post(
        "/v1/runs",
        json=payload(risk="high", evidence=["ticket/T-100/refund-policy"]),
    )
    run_id = created.json()["run_id"]

    response = client.post(
        f"/v1/runs/{run_id}/decision",
        json={
            "decision": "approve",
            "approver": "ops@example.com",
            "reason": "Policy verified",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_decision_for_completed_run_returns_409() -> None:
    client = TestClient(create_app(AgentRuntime()))
    created = client.post("/v1/runs", json=payload())
    run_id = created.json()["run_id"]

    response = client.post(
        f"/v1/runs/{run_id}/decision",
        json={
            "decision": "approve",
            "approver": "ops@example.com",
            "reason": "Not applicable",
        },
    )
    assert response.status_code == 409


def test_idempotency_conflict_returns_409() -> None:
    client = TestClient(create_app(AgentRuntime()))
    first = payload()
    first["idempotency_key"] = "ticket-T-100"
    second = payload()
    second["idempotency_key"] = "ticket-T-100"
    second["goal"] = "different goal"

    assert client.post("/v1/runs", json=first).status_code == 201
    assert client.post("/v1/runs", json=second).status_code == 409


def test_cors_allows_local_nextjs_dashboard() -> None:
    client = TestClient(create_app(AgentRuntime()))
    response = client.options(
        "/v1/runs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
