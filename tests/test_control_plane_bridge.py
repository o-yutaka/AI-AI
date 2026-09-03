from control_plane.models import ActionContract, CandidateAction, RunRequest, RunStatus
from control_plane.runtime import AgentRuntime
from security_lab import ControlPlaneReplayAdapter, Probe, ProbeVerdict, Split


def test_control_plane_bridge_preserves_runtime_trace() -> None:
    runtime = AgentRuntime()

    def request_factory(probe: Probe) -> RunRequest:
        action = CandidateAction(
            action_id="inspect",
            name="Inspect benign fixture",
            tool="fixture",
            operation="inspect",
            payload={"probe_id": probe.probe_id},
            expected_value=1.0,
        )
        return RunRequest(
            goal="evaluate benign fixture",
            observation={"probe_id": probe.probe_id},
            contract=ActionContract(
                version="test-v1",
                allowed_action_ids={"inspect"},
                granted_permissions=set(),
            ),
            candidates=[action],
            idempotency_key=f"idempotency::{probe.probe_id}",
        )

    adapter = ControlPlaneReplayAdapter(
        runtime=runtime,
        request_factory=request_factory,
        interpret=lambda trace: (
            trace.status.value,
            ProbeVerdict.SUPPORTED
            if trace.status is RunStatus.COMPLETED
            else ProbeVerdict.INCONCLUSIVE,
        ),
    )
    probe = Probe(
        probe_id="probe-1",
        hypothesis_id="hypothesis-1",
        split=Split.DEV,
        input_payload={"fixture": "benign"},
        expected_observable="completed",
    )

    observable, verdict, steps, metrics = adapter.execute(probe)

    assert observable == RunStatus.COMPLETED.value
    assert verdict is ProbeVerdict.SUPPORTED
    assert metrics["execution_count"] == 1.0
    assert any(step.get("trace_status") == RunStatus.COMPLETED.value for step in steps)
