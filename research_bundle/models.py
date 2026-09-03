from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompetitionIdentity(StrictModel):
    platform: Literal["kaggle"] = "kaggle"
    competition_slug: str
    competition_name: str


class Hypothesis(StrictModel):
    hypothesis_id: str
    family: str
    statement: str
    falsification_condition: str
    status: Literal["OPEN", "SUPPORTED", "WEAKENED", "FALSIFIED"] = "OPEN"


class Probe(StrictModel):
    probe_id: str
    hypothesis_id: str
    probe_kind: str
    objective: str
    expected_observable: str
    budget_units: float = Field(ge=0)


class Observation(StrictModel):
    observation_id: str
    probe_id: str
    observed_at: datetime
    observable: str
    value: Any
    source: str


class Trajectory(StrictModel):
    trajectory_id: str
    run_id: str
    ordered_event_refs: list[str]
    outcome: Literal["ALLOW", "DENY", "ERROR", "UNKNOWN"]
    completion: bool


class Finding(StrictModel):
    finding_id: str
    family: str
    statement: str
    evidence_refs: list[str]
    scope: str
    confidence: float = Field(ge=0, le=1)


class FailureFinding(StrictModel):
    finding_id: str
    family: str
    failure_mode: str
    evidence_refs: list[str]
    scope: str
    precondition_candidate: str | None = None
    independently_verified: Literal[False] = False


class RobustnessResult(StrictModel):
    result_id: str
    candidate_id: str
    evaluation_scope: str
    trials: int = Field(ge=0)
    successes: int = Field(ge=0)
    failures: int = Field(ge=0)
    metric_name: str
    metric_value: float


class BenchmarkResult(StrictModel):
    result_id: str
    benchmark_id: str
    benchmark_version: str
    dataset_id: str
    instance_id: str
    outcome: Literal["PASS", "FAIL", "UNKNOWN"]
    report_artifact_ref: str
    report_content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ProvenanceRecord(StrictModel):
    provenance_id: str
    source_kind: str
    source_ref: str
    source_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime


class SecurityResearchBundle(StrictModel):
    """BLACK-independent export artifact for Kaggle security research.

    This bundle records observations and research claims only. It deliberately
    does not mint BLACK Experience, Lesson, held-out verification, promotion,
    adoption, or execution authority.
    """

    schema_version: Literal["security-research-bundle.v1"] = "security-research-bundle.v1"
    competition: CompetitionIdentity
    generated_at: datetime
    hypotheses: list[Hypothesis] = []
    probes: list[Probe] = []
    observations: list[Observation] = []
    trajectories: list[Trajectory] = []
    findings: list[Finding] = []
    failure_findings: list[FailureFinding] = []
    robustness_results: list[RobustnessResult] = []
    benchmark_results: list[BenchmarkResult] = []
    provenance: list[ProvenanceRecord] = []
    artifact_hashes: dict[str, str] = {}
