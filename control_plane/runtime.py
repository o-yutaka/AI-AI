from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .models import CandidateAction, DecisionTrace, RiskLevel, RunRequest, RunStatus

Executor = Callable[[CandidateAction], dict[str, Any]]


class AgentRuntime:
    """Selects one valid action, applies policy gates, and preserves an audit trace."""

    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = executor or self._default_executor
        self._runs: dict[str, DecisionTrace] = {}

    @staticmethod
    def _default_executor(action: CandidateAction) -> dict[str, Any]:
        return {"executed": True, "action_id": action.action_id, "payload": action.payload}

    def create_run(self, request: RunRequest) -> DecisionTrace:
        selected = max(request.candidates, key=lambda item: item.expected_value)
        rejected = [
            {"action_id": item.action_id, "reason": "lower_expected_value"}
            for item in request.candidates
            if item.action_id != selected.action_id
        ]

        requires_approval = selected.risk is RiskLevel.HIGH or not selected.reversible
        checks = [
            {"rule": "candidate_from_current_contract", "passed": True},
            {
                "rule": "human_approval_for_high_impact_action",
                "passed": not requires_approval,
                "required": requires_approval,
            },
        ]

        trace = DecisionTrace(
            goal=request.goal,
            observation=request.observation,
            candidates=request.candidates,
            selected_action=selected,
            rejected_actions=rejected,
            policy_checks=checks,
            status=RunStatus.WAITING_APPROVAL if requires_approval else RunStatus.COMPLETED,
        )
        if not requires_approval:
            trace.result = self._executor(selected)

        self._runs[trace.run_id] = trace
        return trace

    def get_run(self, run_id: str) -> DecisionTrace:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise KeyError(f"unknown run_id: {run_id}") from exc

    def approve(self, run_id: str) -> DecisionTrace:
        trace = self.get_run(run_id)
        if trace.status is not RunStatus.WAITING_APPROVAL or trace.selected_action is None:
            raise ValueError("run is not waiting for approval")

        trace.policy_checks.append({"rule": "human_approval_received", "passed": True})
        trace.result = self._executor(trace.selected_action)
        trace.status = RunStatus.COMPLETED
        return trace
