from __future__ import annotations

import json

import httpx

from control_plane.models import ActionContract
from control_plane.providers import (
    OpenAICompatiblePlanner,
    PlannedRunRequest,
    ToolCapability,
)
from control_plane.security import REDACTED


def test_sensitive_observation_is_redacted_before_provider_transmission() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        candidate = {
            "action_id": "reply",
            "name": "Reply",
            "tool": "support_api",
            "operation": "reply",
            "payload": {"ticket_id": "T-100"},
            "expected_value": 0.8,
            "risk": "low",
            "reversible": True,
            "evidence": [],
            "required_permissions": [],
        }
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"candidates": [candidate]})}}
                ]
            },
        )

    planner = OpenAICompatiblePlanner(
        base_url="https://provider.example/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )
    planner.plan(
        PlannedRunRequest(
            goal="Reply to person@example.com",
            observation={
                "ticket_id": "T-100",
                "email": "person@example.com",
                "note": "Call +81 90 1234 5678",
            },
            contract=ActionContract(
                version="support-v1",
                allowed_action_ids={"reply"},
            ),
            tools=[
                ToolCapability(
                    name="support_api",
                    description="Support API",
                    operations=["reply"],
                )
            ],
        )
    )

    user_payload = json.loads(captured["messages"][1]["content"])
    assert user_payload["goal"] == f"Reply to {REDACTED}"
    assert user_payload["observation"]["email"] == REDACTED
    assert REDACTED in user_payload["observation"]["note"]
    serialized = json.dumps(user_payload)
    assert "person@example.com" not in serialized
    assert "+81 90 1234 5678" not in serialized
