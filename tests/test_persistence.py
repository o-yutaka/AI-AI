from pathlib import Path

from control_plane.models import (
    ActionContract,
    ApprovalDecision,
    ApprovalRequest,
    CandidateAction,
    RiskLevel,
    RunRequest,
    RunStatus,
)
from control_plane.runtime import AgentRuntime
from control_plane.store import SQLiteRunRepository


def make_request(*, high_risk: bool = False) -> RunRequest:
    action = CandidateAction(
        action_id="refund" if high_risk else "reply",
        name="refund" if high_risk else "reply",
        tool="support_api",
        operation="refund" if high_risk else "reply",
        risk=RiskLevel.HIGH if high_risk else RiskLevel.LOW,
        reversible=not high_risk,
        evidence=["ticket/T-100/refund-policy"] if high_risk else [],
    )
    return RunRequest(
        goal="resolve customer request",
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={action.action_id},
        ),
        candidates=[action],
        idempotency_key="ticket-T-100",
    )


def repository(path: Path) -> SQLiteRunRepository:
    return SQLiteRunRepository(path)


def test_completed_run_and_idempotency_survive_restart(tmp_path: Path) -> None:
    calls = 0

    def executor(action: CandidateAction) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"action_id": action.action_id}

    path = tmp_path / "control-plane.sqlite3"
    first_repo = repository(path)
    first_runtime = AgentRuntime(executor=executor, repository=first_repo)
    first = first_runtime.create_run(make_request())
    first_repo.close()

    second_repo = repository(path)
    second_runtime = AgentRuntime(executor=executor, repository=second_repo)
    replayed = second_runtime.create_run(make_request())

    assert replayed.run_id == first.run_id
    assert replayed.status is RunStatus.COMPLETED
    assert calls == 1
    second_repo.close()


def test_waiting_approval_can_be_decided_after_restart(tmp_path: Path) -> None:
    path = tmp_path / "control-plane.sqlite3"
    first_repo = repository(path)
    first_runtime = AgentRuntime(repository=first_repo)
    waiting = first_runtime.create_run(make_request(high_risk=True))
    first_repo.close()

    second_repo = repository(path)
    second_runtime = AgentRuntime(repository=second_repo)
    decided = second_runtime.decide(
        waiting.run_id,
        ApprovalRequest(
            decision=ApprovalDecision.APPROVE,
            approver="ops@example.com",
            reason="Evidence verified",
        ),
    )

    assert decided.status is RunStatus.COMPLETED
    assert decided.approval is not None
    assert second_runtime.get_run(waiting.run_id).revision == decided.revision
    second_repo.close()


def test_list_order_and_defensive_deserialization(tmp_path: Path) -> None:
    repo = repository(tmp_path / "control-plane.sqlite3")
    runtime = AgentRuntime(repository=repo)
    first = runtime.create_run(make_request())
    second_request = make_request()
    second_request.idempotency_key = "ticket-T-101"
    second_request.observation["ticket_id"] = "T-101"
    second = runtime.create_run(second_request)

    listed = runtime.list_runs()
    assert [trace.run_id for trace in listed] == [first.run_id, second.run_id]
    listed[0].observation["ticket_id"] = "MUTATED"
    assert runtime.get_run(first.run_id).observation["ticket_id"] == "T-100"
    repo.close()
