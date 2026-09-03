from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from control_plane.models import DecisionTrace, RunRequest
from control_plane.runtime import AgentRuntime

from .models import Probe, ProbeVerdict


RequestFactory = Callable[[Probe], RunRequest]
TraceInterpreter = Callable[[DecisionTrace], tuple[str, ProbeVerdict]]


@dataclass
class ControlPlaneReplayAdapter:
    """Adapt the existing AI-AI control plane to the security-lab ReplayExecutor shape.

    The adapter preserves the control plane as the execution/gating runtime and
    leaves research interpretation explicit. It never auto-approves waiting runs.
    """

    runtime: AgentRuntime
    request_factory: RequestFactory
    interpret: TraceInterpreter

    def execute(
        self,
        probe: Probe,
    ) -> tuple[str, ProbeVerdict, list[dict[str, object]], dict[str, float]]:
        request = self.request_factory(probe)
        trace = self.runtime.create_run(request)
        observable, verdict = self.interpret(trace)
        steps: list[dict[str, object]] = [
            {
                "event_type": event.event_type,
                "details": event.details,
                "at": event.at.isoformat(),
            }
            for event in trace.events
        ]
        steps.append(
            {
                "trace_status": trace.status.value,
                "run_id": trace.run_id,
                "request_fingerprint": trace.request_fingerprint,
                "observation_fingerprint": trace.observation_fingerprint,
                "selected_action_id": (
                    trace.selected_action.action_id if trace.selected_action is not None else None
                ),
            }
        )
        metrics = {
            "execution_count": float(trace.execution_count),
            "eligible_candidates": float(len(trace.eligible_action_ids)),
            "rejected_candidates": float(len(trace.rejected_actions)),
        }
        return observable, verdict, steps, metrics
