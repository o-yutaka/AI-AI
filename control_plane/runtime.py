from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from threading import RLock
from typing import Any

from .errors import IdempotencyConflictError, InvalidRunStateError, UnknownRunError
from .models import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRequest,
    AuditEvent,
    CandidateAction,
    DecisionTrace,
    ExecutionError,
    PolicyCheck,
    RejectedAction,
    RiskLevel,
    RunRequest,
    RunStatus,
    utc_now,
)
from .store import InMemoryRunRepository, RunRepository

Executor = Callable[[CandidateAction], dict[str, Any]]

_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
}


class AgentRuntime:
    """Contract-aware, approval-aware runtime with deterministic audit traces."""

    def __init__(
        self,
        executor: Executor | None = None,
        repository: RunRepository | None = None,
    ) -> None:
        self._executor = executor or self._default_executor
        self._repository = repository or InMemoryRunRepository()
        self._lock = RLock()

    @staticmethod
    def _default_executor(action: CandidateAction) -> dict[str, Any]:
        return {
            "executed": True,
            "action_id": action.action_id,
            "tool": action.tool,
            "operation": action.operation,
            "payload": action.payload,
        }

    @staticmethod
    def _fingerprint(observation: dict[str, Any]) -> str:
        canonical = json.dumps(
            observation,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _request_fingerprint(request: RunRequest) -> str:
        candidates: list[dict[str, Any]] = []
        for candidate in request.candidates:
            candidate_payload = candidate.model_dump(mode="json")
            candidate_payload["required_permissions"] = sorted(
                candidate.required_permissions
            )
            candidates.append(candidate_payload)

        payload = {
            "goal": request.goal,
            "observation": request.observation,
            "contract": {
                "version": request.contract.version,
                "allowed_action_ids": sorted(request.contract.allowed_action_ids),
                "granted_permissions": sorted(request.contract.granted_permissions),
            },
            "candidates": candidates,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _clone(trace: DecisionTrace) -> DecisionTrace:
        return trace.model_copy(deep=True)

    def _store(self, trace: DecisionTrace) -> None:
        self._repository.save(self._clone(trace))

    @staticmethod
    def _rank_candidates(candidates: list[CandidateAction]) -> list[CandidateAction]:
        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.expected_value,
                _RISK_ORDER[candidate.risk],
                not candidate.reversible,
                candidate.action_id,
            ),
        )

    @staticmethod
    def _candidate_reasons(request: RunRequest, candidate: CandidateAction) -> list[str]:
        reasons: list[str] = []
        if candidate.action_id not in request.contract.allowed_action_ids:
            reasons.append("not_in_current_contract")

        missing_permissions = sorted(
            candidate.required_permissions - request.contract.granted_permissions
        )
        if missing_permissions:
            reasons.append(f"missing_permissions:{','.join(missing_permissions)}")

        if candidate.risk is RiskLevel.HIGH and not candidate.evidence:
            reasons.append("missing_evidence_for_high_risk_action")

        return reasons

    def create_run(self, request: RunRequest) -> DecisionTrace:
        with self._lock:
            request_fingerprint = self._request_fingerprint(request)
            if request.idempotency_key:
                existing = self._repository.find_by_idempotency_key(
                    request.idempotency_key
                )
                if existing:
                    if existing.request_fingerprint != request_fingerprint:
                        raise IdempotencyConflictError(
                            "idempotency_key was already used for a different request"
                        )
                    return self._clone(existing)

            rejected: list[RejectedAction] = []
            eligible: list[CandidateAction] = []
            for candidate in request.candidates:
                reasons = self._candidate_reasons(request, candidate)
                if reasons:
                    rejected.append(
                        RejectedAction(action_id=candidate.action_id, reasons=reasons)
                    )
                else:
                    eligible.append(candidate)

            checks = [
                PolicyCheck(
                    rule="current_contract_enforced",
                    passed=all(
                        candidate.action_id in request.contract.allowed_action_ids
                        for candidate in eligible
                    ),
                    details={"contract_version": request.contract.version},
                ),
                PolicyCheck(
                    rule="permissions_enforced",
                    passed=all(
                        candidate.required_permissions
                        <= request.contract.granted_permissions
                        for candidate in eligible
                    ),
                    details={
                        "granted_permissions": sorted(request.contract.granted_permissions)
                    },
                ),
                PolicyCheck(
                    rule="high_risk_evidence_required",
                    passed=all(
                        candidate.risk is not RiskLevel.HIGH or bool(candidate.evidence)
                        for candidate in eligible
                    ),
                ),
            ]

            events = [
                AuditEvent(
                    event_type="run_created",
                    details={"candidate_count": len(request.candidates)},
                )
            ]

            trace = DecisionTrace(
                idempotency_key=request.idempotency_key,
                goal=request.goal,
                observation=request.observation,
                observation_fingerprint=self._fingerprint(request.observation),
                request_fingerprint=request_fingerprint,
                contract_version=request.contract.version,
                candidates=request.candidates,
                eligible_action_ids=[candidate.action_id for candidate in eligible],
                rejected_actions=rejected,
                policy_checks=checks,
                events=events,
                status=RunStatus.BLOCKED,
            )

            if not eligible:
                trace.events.append(
                    AuditEvent(
                        event_type="run_blocked",
                        details={"reason": "no_eligible_actions"},
                    )
                )
                self._store(trace)
                return self._clone(trace)

            ranked = self._rank_candidates(eligible)
            selected = ranked[0]
            trace.selected_action = selected
            for candidate in ranked[1:]:
                trace.rejected_actions.append(
                    RejectedAction(
                        action_id=candidate.action_id,
                        reasons=["lower_deterministic_rank"],
                    )
                )

            requires_approval = selected.risk is RiskLevel.HIGH or not selected.reversible
            trace.policy_checks.append(
                PolicyCheck(
                    rule="high_impact_action_requires_approval",
                    passed=True,
                    details={"required": requires_approval},
                )
            )
            trace.events.append(
                AuditEvent(
                    event_type="action_selected",
                    details={"action_id": selected.action_id},
                )
            )

            if requires_approval:
                trace.status = RunStatus.WAITING_APPROVAL
                trace.events.append(
                    AuditEvent(
                        event_type="approval_requested",
                        details={"action_id": selected.action_id},
                    )
                )
            else:
                self._execute(trace)

            self._store(trace)
            return self._clone(trace)

    def _execute(self, trace: DecisionTrace) -> None:
        selected = trace.selected_action
        if selected is None:
            raise InvalidRunStateError("cannot execute a run without a selected action")

        try:
            trace.result = self._executor(selected)
        except Exception as exc:  # noqa: BLE001 - runtime must preserve external failures
            trace.status = RunStatus.FAILED
            trace.error = ExecutionError(
                error_type=type(exc).__name__,
                message=str(exc),
            )
            trace.events.append(
                AuditEvent(
                    event_type="execution_failed",
                    details={"error_type": type(exc).__name__},
                )
            )
        else:
            trace.status = RunStatus.COMPLETED
            trace.error = None
            trace.events.append(
                AuditEvent(
                    event_type="action_executed",
                    details={"action_id": selected.action_id},
                )
            )
        finally:
            trace.updated_at = utc_now()
            trace.revision += 1

    def get_run(self, run_id: str) -> DecisionTrace:
        with self._lock:
            trace = self._repository.get(run_id)
            if trace is None:
                raise UnknownRunError(f"unknown run_id: {run_id}")
            return self._clone(trace)

    def list_runs(self) -> list[DecisionTrace]:
        with self._lock:
            return [self._clone(trace) for trace in self._repository.list()]

    def decide(self, run_id: str, request: ApprovalRequest) -> DecisionTrace:
        with self._lock:
            trace = self._repository.get(run_id)
            if trace is None:
                raise UnknownRunError(f"unknown run_id: {run_id}")
            trace = self._clone(trace)

            if trace.status is not RunStatus.WAITING_APPROVAL:
                raise InvalidRunStateError("run is not waiting for approval")

            trace.approval = ApprovalRecord(
                decision=request.decision,
                approver=request.approver,
                reason=request.reason,
            )
            trace.updated_at = utc_now()
            trace.revision += 1

            if request.decision is ApprovalDecision.REJECT:
                trace.status = RunStatus.REJECTED
                trace.events.append(
                    AuditEvent(
                        event_type="approval_rejected",
                        details={"approver": request.approver},
                    )
                )
            else:
                trace.events.append(
                    AuditEvent(
                        event_type="approval_granted",
                        details={"approver": request.approver},
                    )
                )
                self._execute(trace)

            self._store(trace)
            return self._clone(trace)
