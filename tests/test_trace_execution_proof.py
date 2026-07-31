from __future__ import annotations

from control_plane.models import ActionContract, CandidateAction, RunRequest, RunStatus
from control_plane.runtime import AgentRuntime


def request(*, key: str = "stable-key", goal: str = "reply") -> RunRequest:
    return RunRequest(
        goal=goal,
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={"reply"},
        ),
        candidates=[
            CandidateAction(
                action_id="reply",
                name="Reply",
                tool="support_api",
                operation="reply",
                payload={"ticket_id": "T-100"},
            )
        ],
        idempotency_key=key,
    )


def test_duplicate_response_proves_no_second_execution() -> None:
    calls = 0

    def executor(action: CandidateAction) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"action_id": action.action_id}

    runtime = AgentRuntime(executor=executor)
    first = runtime.create_run(request())
    replay = runtime.create_run(request())
    persisted = runtime.get_run(first.run_id)

    assert first.status is RunStatus.COMPLETED
    assert first.execution_count == 1
    assert first.idempotency_replayed is False
    assert replay.run_id == first.run_id
    assert replay.execution_count == 1
    assert replay.idempotency_replayed is True
    assert replay.events[-1].event_type == "idempotency_replay"
    assert replay.events[-1].details["no_second_execution"] is True
    assert persisted.idempotency_replayed is False
    assert calls == 1


def test_blocked_run_has_zero_execution_count() -> None:
    body = request()
    body.contract = ActionContract(
        version="support-v1",
        allowed_action_ids={"other"},
    )

    trace = AgentRuntime().create_run(body)

    assert trace.status is RunStatus.BLOCKED
    assert trace.execution_count == 0


def test_failed_executor_counts_one_attempt() -> None:
    def executor(action: CandidateAction) -> dict[str, object]:
        raise TimeoutError(action.action_id)

    trace = AgentRuntime(executor=executor).create_run(request())

    assert trace.status is RunStatus.FAILED
    assert trace.execution_count == 1
