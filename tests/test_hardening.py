from __future__ import annotations

from control_plane.models import ActionContract, CandidateAction, RunRequest, RunStatus
from control_plane.runtime import AgentRuntime
from control_plane.security import REDACTED


def make_request(candidate: CandidateAction, *, observation: dict | None = None) -> RunRequest:
    return RunRequest(
        goal="perform one governed action",
        observation=observation or {"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={candidate.action_id},
            granted_permissions=candidate.required_permissions,
        ),
        candidates=[candidate],
    )


def test_sensitive_payload_is_blocked_and_redacted_before_storage() -> None:
    candidate = CandidateAction(
        action_id="reply",
        name="Reply",
        tool="support_api",
        operation="reply",
        payload={"ticket_id": "T-100", "password": "must-not-persist"},
    )
    runtime = AgentRuntime()

    trace = runtime.create_run(
        make_request(candidate, observation={"email": "person@example.com"})
    )

    assert trace.status is RunStatus.BLOCKED
    assert trace.observation["email"] == REDACTED
    assert trace.candidates[0].payload["password"] == REDACTED
    assert "must-not-persist" not in trace.model_dump_json()
    assert "person@example.com" not in trace.model_dump_json()
    assert trace.rejected_actions[0].reasons == [
        "sensitive_payload_keys:$.password"
    ]


def test_unregistered_tool_operation_is_blocked_before_execution() -> None:
    calls = 0

    def executor(action: CandidateAction) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"action_id": action.action_id}

    candidate = CandidateAction(
        action_id="exfiltrate",
        name="Exfiltrate",
        tool="shadow_api",
        operation="exfiltrate",
        payload={"record_id": "R-1"},
    )
    runtime = AgentRuntime(
        executor=executor,
        allowed_tool_operations={("support_api", "reply")},
    )

    trace = runtime.create_run(make_request(candidate))

    assert trace.status is RunStatus.BLOCKED
    assert calls == 0
    assert trace.rejected_actions[0].reasons == [
        "unregistered_tool_operation:shadow_api.exfiltrate"
    ]


def test_executor_result_is_redacted_before_return_and_persistence() -> None:
    def executor(action: CandidateAction) -> dict[str, object]:
        return {
            "action_id": action.action_id,
            "token": "runtime-secret",
            "customer": {"email": "person@example.com"},
        }

    candidate = CandidateAction(
        action_id="reply",
        name="Reply",
        tool="support_api",
        operation="reply",
        payload={"ticket_id": "T-100"},
    )
    runtime = AgentRuntime(executor=executor)

    trace = runtime.create_run(make_request(candidate))
    stored = runtime.get_run(trace.run_id)

    assert trace.status is RunStatus.COMPLETED
    assert trace.result["token"] == REDACTED
    assert trace.result["customer"]["email"] == REDACTED
    assert "runtime-secret" not in stored.model_dump_json()
    assert "person@example.com" not in stored.model_dump_json()


def test_executor_error_message_redacts_credentials() -> None:
    def executor(action: CandidateAction) -> dict[str, object]:
        raise RuntimeError("Authorization: Bearer abc.def token=secret-value")

    candidate = CandidateAction(
        action_id="reply",
        name="Reply",
        tool="support_api",
        operation="reply",
        payload={"ticket_id": "T-100"},
    )
    trace = AgentRuntime(executor=executor).create_run(make_request(candidate))

    assert trace.status is RunStatus.FAILED
    assert trace.error is not None
    assert "abc.def" not in trace.error.message
    assert "secret-value" not in trace.error.message
    assert "[REDACTED]" in trace.error.message
