from __future__ import annotations

import json

import httpx
import pytest

from control_plane.models import ActionContract
from control_plane.providers import (
    OpenAICompatiblePlanner,
    PlannedRunRequest,
    ProviderResponseError,
    ToolCapability,
)


def request() -> PlannedRunRequest:
    return PlannedRunRequest(
        goal="Resolve the support ticket",
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={"reply"},
            granted_permissions={"ticket:write"},
        ),
        tools=[
            ToolCapability(
                name="support_api",
                description="Customer support API",
                operations=["reply"],
                input_schema={"type": "object"},
            )
        ],
        idempotency_key="provider-T-100",
    )


def candidate_payload(*, tool: str = "support_api", operation: str = "reply") -> dict:
    return {
        "action_id": "reply",
        "name": "Reply to customer",
        "tool": tool,
        "operation": operation,
        "payload": {"ticket_id": "T-100", "message": "Resolved"},
        "expected_value": 0.9,
        "risk": "low",
        "reversible": True,
        "evidence": ["knowledge-base/article-12"],
        "required_permissions": ["ticket:write"],
    }


def test_openai_compatible_planner_returns_validated_candidates() -> None:
    captured: dict = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        captured["url"] = str(http_request.url)
        captured["authorization"] = http_request.headers.get("authorization")
        captured["body"] = json.loads(http_request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"candidates": [candidate_payload()]}
                            )
                        }
                    }
                ]
            },
        )

    planner = OpenAICompatiblePlanner(
        base_url="https://provider.example/v1/",
        model="frontier-code",
        api_key="test-secret",
        transport=httpx.MockTransport(handler),
    )
    result = planner.plan(request())

    assert captured["url"] == "https://provider.example/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-secret"
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "Do not include credentials" in captured["body"]["messages"][0]["content"]
    assert result.provider == "openai-compatible"
    assert result.model == "frontier-code"
    assert result.candidates[0].action_id == "reply"


def test_provider_cannot_invent_an_undeclared_tool_operation() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "candidates": [
                                        candidate_payload(tool="billing_api", operation="refund")
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    planner = OpenAICompatiblePlanner(
        base_url="https://provider.example/v1",
        model="frontier-code",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderResponseError, match="undeclared"):
        planner.plan(request())


def test_provider_rejects_malformed_candidate_content() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    planner = OpenAICompatiblePlanner(
        base_url="https://provider.example/v1",
        model="frontier-code",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderResponseError, match="CandidateAction"):
        planner.plan(request())


def test_provider_aborts_when_stream_crosses_response_limit() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b"x" * 2048,
        )

    planner = OpenAICompatiblePlanner(
        base_url="https://provider.example/v1",
        model="frontier-code",
        max_response_bytes=1024,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderResponseError, match="size limit"):
        planner.plan(request())
