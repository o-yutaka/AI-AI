from __future__ import annotations

import pytest
from pydantic import ValidationError

from control_plane.errors import IdempotencyConflictError, InvalidRunStateError
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
from control_plane.security import REDACTED


def candidate(
    action_id: str,
    *,
    value: float = 0.5,
    risk: RiskLevel = RiskLevel.LOW,
    reversible: bool = True,
    evidence: list[str] | None = None,
    permissions: set[str] | None = None,
) -> CandidateAction:
    return CandidateAction(
        action_id=action_id,
        name=action_id,
        tool="support_api",
        operation=action_id,
        expected_value=value,
        risk=risk,
        reversible=reversible,
        evidence=evidence or [],
        required_permissions=permissions or set(),
    )


def request_for(
    *candidates: CandidateAction,
    allowed: set[str] | None = None,
    permissions: set[str] | None = None,
    idempotency_key: str | None = None,
) -> RunRequest:
    return RunRequest(
        goal="resolve customer request",
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids=allowed or {item.action_id for item in candidates},
            granted_permissions=permissions or set(),
        ),
        candidates=list(candidates),
        idempotency_key=idempotency_key,
    )


def test_executes_highest_ranked_eligible_action() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(candidate("reply", value=0.8), candidate("escalate", value=0.4))
    )

    assert trace.status is RunStatus.COMPLETED
    assert trace.selected_action is not None
    assert trace.selected_action.action_id == "reply"
    assert trace.result["executed"] is True
    assert any(
        rejected.action_id == "escalate"
        and rejected.reasons == ["lower_deterministic_rank"]
        for rejected in trace.rejected_actions
    )


def test_filters_action_not_in_current_contract() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(
            candidate("refund", value=1.0),
            candidate("reply", value=0.5),
            allowed={"reply"},
        )
    )

    assert trace.selected_action is not None
    assert trace.selected_action.action_id == "reply"
    assert any(
        rejected.action_id == "refund"
        and "not_in_current_contract" in rejected.reasons
        for rejected in trace.rejected_actions
    )


def test_filters_action_when_permission_is_missing() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(
            candidate("refund", value=1.0, permissions={"refund:write"}),
            candidate("reply", value=0.5),
        )
    )

    assert trace.selected_action is not None
    assert trace.selected_action.action_id == "reply"
    assert any(
        rejected.action_id == "refund"
        and "missing_permissions:refund:write" in rejected.reasons
        for rejected in trace.rejected_actions
    )


def test_blocks_when_no_candidate_is_eligible() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(candidate("refund", permissions={"refund:write"}))
    )

    assert trace.status is RunStatus.BLOCKED
    assert trace.selected_action is None
    assert trace.result == {}


def test_high_risk_action_without_evidence_is_blocked() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(candidate("refund", risk=RiskLevel.HIGH))
    )

    assert trace.status is RunStatus.BLOCKED
    assert trace.selected_action is None
    assert trace.rejected_actions[0].reasons == [
        "missing_evidence_for_high_risk_action"
    ]


def test_high_risk_action_requires_named_approval() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(
            candidate(
                "refund",
                value=1.0,
                risk=RiskLevel.HIGH,
                reversible=False,
                evidence=["ticket/T-100/refund-policy"],
            )
        )
    )

    assert trace.status is RunStatus.WAITING_APPROVAL
    assert trace.result == {}

    decided = runtime.decide(
        trace.run_id,
        ApprovalRequest(
            decision=ApprovalDecision.APPROVE,
            approver="ops@example.com",
            reason="Verified against refund policy",
        ),
    )
    assert decided.status is RunStatus.COMPLETED
    assert decided.approval is not None
    assert decided.approval.approver == REDACTED
    assert decided.result["action_id"] == "refund"
    assert "ops@example.com" not in decided.model_dump_json()


def test_rejected_approval_never_executes() -> None:
    calls = 0

    def executor(action: CandidateAction) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"action_id": action.action_id}

    runtime = AgentRuntime(executor=executor)
    trace = runtime.create_run(
        request_for(
            candidate(
                "refund",
                risk=RiskLevel.HIGH,
                evidence=["ticket/T-100/refund-policy"],
            )
        )
    )
    decided = runtime.decide(
        trace.run_id,
        ApprovalRequest(
            decision=ApprovalDecision.REJECT,
            approver="ops@example.com",
            reason="Evidence is insufficient",
        ),
    )

    assert decided.status is RunStatus.REJECTED
    assert decided.result == {}
    assert calls == 0


def test_duplicate_action_ids_are_rejected_at_input_boundary() -> None:
    with pytest.raises(ValidationError):
        request_for(candidate("reply"), candidate("reply"))


def test_tie_breaking_is_deterministic() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(candidate("b", value=1.0), candidate("a", value=1.0))
    )

    assert trace.selected_action is not None
    assert trace.selected_action.action_id == "a"


def test_idempotency_executes_once_and_returns_same_run() -> None:
    calls = 0

    def executor(action: CandidateAction) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"action_id": action.action_id}

    runtime = AgentRuntime(executor=executor)
    request = request_for(candidate("reply"), idempotency_key="ticket-T-100")
    first = runtime.create_run(request)
    second = runtime.create_run(request)

    assert first.run_id == second.run_id
    assert calls == 1


def test_request_fingerprint_is_stable_across_set_insertion_order() -> None:
    runtime = AgentRuntime()
    first = RunRequest(
        goal="resolve customer request",
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={"reply", "escalate"},
            granted_permissions={"ticket:write", "ticket:read"},
        ),
        candidates=[
            candidate(
                "reply",
                permissions={"ticket:read", "ticket:write"},
            )
        ],
        idempotency_key="stable-set-order",
    )
    second = RunRequest(
        goal="resolve customer request",
        observation={"ticket_id": "T-100"},
        contract=ActionContract(
            version="support-v1",
            allowed_action_ids={"escalate", "reply"},
            granted_permissions={"ticket:read", "ticket:write"},
        ),
        candidates=[
            candidate(
                "reply",
                permissions={"ticket:write", "ticket:read"},
            )
        ],
        idempotency_key="stable-set-order",
    )

    first_trace = runtime.create_run(first)
    second_trace = runtime.create_run(second)
    assert first_trace.run_id == second_trace.run_id


def test_idempotency_key_rejects_different_request() -> None:
    runtime = AgentRuntime()
    first = request_for(candidate("reply"), idempotency_key="ticket-T-100")
    second = request_for(candidate("escalate"), idempotency_key="ticket-T-100")
    runtime.create_run(first)

    with pytest.raises(IdempotencyConflictError):
        runtime.create_run(second)


def test_executor_failure_is_recorded_in_trace() -> None:
    def failing_executor(action: CandidateAction) -> dict[str, object]:
        raise TimeoutError(f"timeout while executing {action.action_id}")

    runtime = AgentRuntime(executor=failing_executor)
    trace = runtime.create_run(request_for(candidate("reply")))

    assert trace.status is RunStatus.FAILED
    assert trace.error is not None
    assert trace.error.error_type == "TimeoutError"
    assert "timeout" in trace.error.message


def test_second_decision_is_rejected() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        request_for(
            candidate(
                "refund",
                risk=RiskLevel.HIGH,
                evidence=["ticket/T-100/refund-policy"],
            )
        )
    )
    decision = ApprovalRequest(
        decision=ApprovalDecision.REJECT,
        approver="operator-id",
        reason="Rejected",
    )
    runtime.decide(trace.run_id, decision)

    with pytest.raises(InvalidRunStateError):
        runtime.decide(trace.run_id, decision)


def test_get_run_returns_a_defensive_copy() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(request_for(candidate("reply")))
    retrieved = runtime.get_run(trace.run_id)
    retrieved.observation["ticket_id"] = "MUTATED"

    stored = runtime.get_run(trace.run_id)
    assert stored.observation["ticket_id"] == "T-100"
