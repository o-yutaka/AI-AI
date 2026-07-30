from control_plane.models import CandidateAction, RiskLevel, RunRequest, RunStatus
from control_plane.runtime import AgentRuntime


def test_selects_highest_value_low_risk_action() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        RunRequest(
            goal="resolve request",
            candidates=[
                CandidateAction(action_id="a", name="reply", expected_value=0.7),
                CandidateAction(action_id="b", name="escalate", expected_value=0.4),
            ],
        )
    )

    assert trace.status is RunStatus.COMPLETED
    assert trace.selected_action is not None
    assert trace.selected_action.action_id == "a"
    assert trace.result["executed"] is True


def test_high_risk_action_requires_approval() -> None:
    runtime = AgentRuntime()
    trace = runtime.create_run(
        RunRequest(
            goal="issue refund",
            candidates=[
                CandidateAction(
                    action_id="refund",
                    name="refund customer",
                    expected_value=1.0,
                    risk=RiskLevel.HIGH,
                    reversible=False,
                )
            ],
        )
    )

    assert trace.status is RunStatus.WAITING_APPROVAL
    assert trace.result == {}

    approved = runtime.approve(trace.run_id)
    assert approved.status is RunStatus.COMPLETED
    assert approved.result["action_id"] == "refund"
