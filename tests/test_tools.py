from __future__ import annotations

import httpx
import pytest

from control_plane.models import CandidateAction
from control_plane.security import REDACTED
from control_plane.tools import (
    HttpJsonToolAdapter,
    HttpOperation,
    HttpToolConfig,
    ToolExecutionError,
    ToolRegistryExecutor,
)


def action(
    *,
    operation: str = "reply",
    tool: str = "support_api",
    payload: dict | None = None,
) -> CandidateAction:
    return CandidateAction(
        action_id="reply",
        name="Reply to customer",
        tool=tool,
        operation=operation,
        payload=payload or {"ticket_id": "T/100", "message": "Resolved"},
        expected_value=0.9,
    )


def config(*, max_response_bytes: int = 262_144) -> HttpToolConfig:
    return HttpToolConfig(
        base_url="https://support.example",
        headers={"Authorization": "Bearer ${SUPPORT_API_TOKEN}"},
        max_response_bytes=max_response_bytes,
        operations={
            "reply": HttpOperation(
                method="POST",
                path="/tickets/{ticket_id}/reply",
                payload_mode="json",
            )
        },
    )


def test_http_adapter_uses_fixed_host_method_path_and_secret() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"ticket_id": "T/100", "sent": True},
        )

    adapter = HttpJsonToolAdapter(
        config(),
        environment={"SUPPORT_API_TOKEN": "secret-token"},
        transport=httpx.MockTransport(handler),
    )
    result = adapter.execute(action())

    assert captured["method"] == "POST"
    assert captured["url"] == "https://support.example/tickets/T%2F100/reply"
    assert captured["authorization"] == "Bearer secret-token"
    assert '"message":"Resolved"' in captured["body"]
    assert result["executed"] is True
    assert result["response"]["sent"] is True


def test_http_adapter_denies_unconfigured_operation() -> None:
    adapter = HttpJsonToolAdapter(config(), environment={"SUPPORT_API_TOKEN": "secret"})

    with pytest.raises(ToolExecutionError, match="not configured"):
        adapter.execute(action(operation="delete_account"))


def test_tool_registry_denies_unregistered_tool() -> None:
    adapter = HttpJsonToolAdapter(config(), environment={"SUPPORT_API_TOKEN": "secret"})
    executor = ToolRegistryExecutor({"support_api": adapter})

    with pytest.raises(ToolExecutionError, match="not registered"):
        executor(action(tool="billing_api"))


def test_tool_registry_exposes_exact_capabilities() -> None:
    adapter = HttpJsonToolAdapter(config(), environment={"SUPPORT_API_TOKEN": "secret"})
    executor = ToolRegistryExecutor({"support_api": adapter})

    assert executor.capabilities == frozenset({("support_api", "reply")})
    assert executor.supports(action()) is True
    assert executor.supports(action(operation="delete_account")) is False


def test_http_adapter_requires_referenced_secret() -> None:
    adapter = HttpJsonToolAdapter(config(), environment={})

    with pytest.raises(ToolExecutionError, match="SUPPORT_API_TOKEN"):
        adapter.execute(action())


def test_http_adapter_rejects_sensitive_payload_values() -> None:
    adapter = HttpJsonToolAdapter(
        config(),
        environment={"SUPPORT_API_TOKEN": "secret"},
    )

    with pytest.raises(ToolExecutionError, match="sensitive values"):
        adapter.execute(
            action(payload={"ticket_id": "T-100", "email": "person@example.com"})
        )


def test_http_adapter_aborts_when_stream_crosses_response_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/octet-stream"},
            content=b"x" * 2048,
        )

    adapter = HttpJsonToolAdapter(
        config(max_response_bytes=1024),
        environment={"SUPPORT_API_TOKEN": "secret"},
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ToolExecutionError, match="size limit"):
        adapter.execute(action())


def test_http_adapter_redacts_sensitive_response_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={
                "ticket_id": "T-100",
                "token": "must-not-leak",
                "customer": {"email": "person@example.com"},
            },
        )

    adapter = HttpJsonToolAdapter(
        config(),
        environment={"SUPPORT_API_TOKEN": "secret"},
        transport=httpx.MockTransport(handler),
    )
    result = adapter.execute(action())

    assert result["response"]["token"] == REDACTED
    assert result["response"]["customer"]["email"] == REDACTED
    assert "must-not-leak" not in str(result)
    assert "person@example.com" not in str(result)
