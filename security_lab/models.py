from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Split(StrEnum):
    TRAIN = "TRAIN"
    DEV = "DEV"
    HELD_OUT = "HELD_OUT"
    ADVERSARIAL_HELD_OUT = "ADVERSARIAL_HELD_OUT"


class ProbeVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class EnvironmentIdentity:
    model_id: str
    runtime_id: str
    quantization: str | None = None
    tool_surface_hash: str | None = None
    evaluator_hash: str | None = None
    model_revision: str | None = None
    runtime_version: str | None = None
    tokenizer_revision: str | None = None
    compiler_id: str | None = None


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    family_id: str
    statement: str
    falsification_condition: str
    expected_observable: str
    prior: float = 0.5


@dataclass(frozen=True)
class Probe:
    probe_id: str
    hypothesis_id: str
    split: Split
    input_payload: dict[str, Any]
    expected_observable: str
    budget_cost: float = 1.0


@dataclass(frozen=True)
class Observation:
    observation_id: str
    probe_id: str
    observable: str
    verdict: ProbeVerdict
    metrics: dict[str, float] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Trajectory:
    trajectory_id: str
    probe_id: str
    environment: EnvironmentIdentity
    steps: tuple[dict[str, Any], ...]
    token_count: int = 0
    latency_ms: float = 0.0
    completed: bool = True


@dataclass(frozen=True)
class FamilyResult:
    family_id: str
    support_score: float
    sample_count: int
    eliminated: bool
    reason: str
