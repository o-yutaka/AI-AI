from __future__ import annotations

import httpx
import pytest

from control_plane.models import CandidateAction
from control_plane.tools import (
    HttpJsonToolAdapter,
    HttpOperation,
    HttpToolConfig,
    ToolExecutionError,
    ToolRegistryExecutor,
)


def action(*, operation: str = "reply", tool: str = "support_api") -> CandidateAction:
    return CandidateAction(
        action_id="reply",
        name="Reply to customer",
        tool=tool,
        operation=operation,
        payload={"ticket_id": "T/100", "message": "Resolved"},
        expected_value=0.9,
    )


def config() -> HttpToolConfig:
    return HttpToolConfig(
        base_url="https://support.example",
        headers={"Authorization": "Bearer ${SUPPORT_API_TOKEN}"},
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


def test_http_adapter_requires_referenced_secret() -> None:
    adapter = HttpJsonToolAdapter(config(), environment={})

    with pytest.raises(ToolExecutionError, match="SUPPORT_API_TOKEN"):
        adapter.execute(action())
