from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import EnvironmentIdentity, ProbeVerdict
from .replay import ReplayResult
from .reproducibility import stable_hash


@dataclass(frozen=True)
class TargetReplayExpectation:
    environment: EnvironmentIdentity
    required_verdict: ProbeVerdict = ProbeVerdict.SUPPORTED
    required_observable: str | None = None
    require_completed: bool = True


@dataclass(frozen=True)
class TargetReplayVerdict:
    passed: bool
    reason_codes: tuple[str, ...]
    expected_environment_hash: str
    observed_environment_hash: str


def evaluate_target_replay(
    expectation: TargetReplayExpectation,
    replay: ReplayResult,
) -> TargetReplayVerdict:
    """Apply an exact-runtime hard gate to a materialized replay result.

    This is a research verification boundary only. Passing it does not imply
    independent verification, adoption, promotion, routing, or execution
    authority outside this repository.
    """

    reasons: list[str] = []
    expected_hash = _environment_hash(expectation.environment)
    observed_hash = _environment_hash(replay.trajectory.environment)

    if replay.trajectory.environment != expectation.environment:
        reasons.append("environment_identity_mismatch")
    if replay.trajectory.probe_id != replay.observation.probe_id:
        reasons.append("probe_binding_mismatch")
    if replay.trajectory.trajectory_id not in replay.observation.evidence_refs:
        reasons.append("trajectory_evidence_unbound")
    if replay.observation.verdict is not expectation.required_verdict:
        reasons.append("required_verdict_missing")
    if (
        expectation.required_observable is not None
        and replay.observation.observable != expectation.required_observable
    ):
        reasons.append("required_observable_mismatch")
    if expectation.require_completed and not replay.trajectory.completed:
        reasons.append("trajectory_incomplete")

    return TargetReplayVerdict(
        passed=not reasons,
        reason_codes=tuple(sorted(reasons)),
        expected_environment_hash=expected_hash,
        observed_environment_hash=observed_hash,
    )


def _environment_hash(environment: EnvironmentIdentity) -> str:
    return stable_hash(asdict(environment))
