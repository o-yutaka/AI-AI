from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RunStatus(str, Enum):
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


class ActionContract(BaseModel):
    """Current external-system contract and caller permissions."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(min_length=1, max_length=128)
    allowed_action_ids: set[str] = Field(min_length=1)
    granted_permissions: set[str] = Field(default_factory=set)


class CandidateAction(BaseModel):
    """A caller-supplied action candidate that still must pass runtime policy checks."""

    model_config = ConfigDict(frozen=True)

    action_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    tool: str = Field(min_length=1, max_length=128)
    operation: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_value: float = Field(default=0.0, allow_inf_nan=False)
    risk: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    evidence: list[str] = Field(default_factory=list)
    required_permissions: set[str] = Field(default_factory=set)


class RunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    observation: dict[str, Any] = Field(default_factory=dict)
    contract: ActionContract
    candidates: list[CandidateAction] = Field(min_length=1, max_length=100)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_unique_action_ids(self) -> RunRequest:
        action_ids = [candidate.action_id for candidate in self.candidates]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("candidate action_id values must be unique")
        return self


class ApprovalRequest(BaseModel):
    decision: ApprovalDecision
    approver: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)


class RejectedAction(BaseModel):
    action_id: str
    reasons: list[str]


class PolicyCheck(BaseModel):
    rule: str
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    event_type: str
    at: datetime = Field(default_factory=utc_now)
    details: dict[str, Any] = Field(default_factory=dict)


class ApprovalRecord(BaseModel):
    decision: ApprovalDecision
    approver: str
    reason: str
    decided_at: datetime = Field(default_factory=utc_now)


class ExecutionError(BaseModel):
    error_type: str
    message: str


class DecisionTrace(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    revision: int = 1
    idempotency_key: str | None = None
    goal: str
    observation: dict[str, Any]
    observation_fingerprint: str
    contract_version: str
    candidates: list[CandidateAction]
    eligible_action_ids: list[str] = Field(default_factory=list)
    selected_action: CandidateAction | None = None
    rejected_actions: list[RejectedAction] = Field(default_factory=list)
    policy_checks: list[PolicyCheck] = Field(default_factory=list)
    approval: ApprovalRecord | None = None
    events: list[AuditEvent] = Field(default_factory=list)
    status: RunStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error: ExecutionError | None = None
