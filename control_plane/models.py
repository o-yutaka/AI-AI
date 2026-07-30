from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RunStatus(str, Enum):
    COMPLETED = "completed"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    FAILED = "failed"


class CandidateAction(BaseModel):
    action_id: str
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    expected_value: float = 0.0
    risk: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    evidence: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    goal: str = Field(min_length=1)
    observation: dict[str, Any] = Field(default_factory=dict)
    candidates: list[CandidateAction] = Field(min_length=1)


class DecisionTrace(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    goal: str
    observation: dict[str, Any]
    candidates: list[CandidateAction]
    selected_action: CandidateAction | None = None
    rejected_actions: list[dict[str, str]] = Field(default_factory=list)
    policy_checks: list[dict[str, Any]] = Field(default_factory=list)
    status: RunStatus
    result: dict[str, Any] = Field(default_factory=dict)
