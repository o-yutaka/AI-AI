from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class ReplayWallOutcome(StrEnum):
    COMPLETE = "COMPLETE"
    FORFEIT = "FORFEIT"


@dataclass(frozen=True)
class ReplayWallObservation:
    environment_key: str
    candidate_count: int
    budget_seconds: float
    outcome: ReplayWallOutcome

    def __post_init__(self) -> None:
        if not self.environment_key:
            raise ValueError("environment_key must be non-empty")
        if self.candidate_count < 1:
            raise ValueError("candidate_count must be positive")
        if self.budget_seconds <= 0 or not isfinite(self.budget_seconds):
            raise ValueError("budget_seconds must be finite and positive")

    @property
    def implied_seconds_per_candidate(self) -> float:
        return self.budget_seconds / self.candidate_count


@dataclass(frozen=True)
class ReplayWallCalibration:
    environment_key: str
    lower_cost_exclusive_seconds: float
    upper_cost_inclusive_seconds: float
    observation_count: int
    complete_count: int
    forfeit_count: int

    def __post_init__(self) -> None:
        if not self.environment_key:
            raise ValueError("environment_key must be non-empty")
        if self.lower_cost_exclusive_seconds < 0:
            raise ValueError("lower replay cost bound must be non-negative")
        if self.upper_cost_inclusive_seconds <= 0:
            raise ValueError("upper replay cost bound must be positive")
        if self.lower_cost_exclusive_seconds >= self.upper_cost_inclusive_seconds:
            raise ValueError("replay-wall bounds are empty or inconsistent")
        if self.observation_count < 1:
            raise ValueError("observation_count must be positive")


@dataclass(frozen=True)
class ReplayWallRiskPoint:
    candidate_count: int
    budget_seconds: float
    forfeit_probability: float
    threshold_seconds_per_candidate: float


@dataclass(frozen=True)
class ReplayWallPlan:
    environment_key: str
    budget_seconds: float
    target_forfeit_probability: float
    max_candidates: int
    risk_at_max_candidates: float
    next_candidate_risk: float | None


def calibrate_replay_wall(
    observations: list[ReplayWallObservation],
    *,
    prior_cost_floor_seconds: float = 0.0,
    prior_cost_ceiling_seconds: float | None = None,
) -> ReplayWallCalibration:
    """Infer a censored per-candidate replay-cost interval from atomic outcomes.

    A COMPLETE observation implies average replay cost <= budget / candidate_count.
    A FORFEIT observation implies average replay cost > budget / candidate_count.
    The interval is deliberately conservative and does not claim a point estimate.
    """

    if not observations:
        raise ValueError("replay-wall calibration requires at least one observation")
    if prior_cost_floor_seconds < 0 or not isfinite(prior_cost_floor_seconds):
        raise ValueError("prior_cost_floor_seconds must be finite and non-negative")
    if prior_cost_ceiling_seconds is not None:
        if prior_cost_ceiling_seconds <= 0 or not isfinite(prior_cost_ceiling_seconds):
            raise ValueError("prior_cost_ceiling_seconds must be finite and positive")
        if prior_cost_floor_seconds >= prior_cost_ceiling_seconds:
            raise ValueError("prior replay-cost bounds are inconsistent")

    environments = {item.environment_key for item in observations}
    if len(environments) != 1:
        raise ValueError("replay-wall observations must share one exact environment_key")

    lower = prior_cost_floor_seconds
    upper = prior_cost_ceiling_seconds
    complete_count = 0
    forfeit_count = 0
    for item in observations:
        implied = item.implied_seconds_per_candidate
        if item.outcome is ReplayWallOutcome.COMPLETE:
            complete_count += 1
            upper = implied if upper is None else min(upper, implied)
        elif item.outcome is ReplayWallOutcome.FORFEIT:
            forfeit_count += 1
            lower = max(lower, implied)
        else:  # pragma: no cover - StrEnum construction already constrains this
            raise ValueError(f"unsupported replay-wall outcome: {item.outcome}")

    if upper is None:
        raise ValueError(
            "replay-wall calibration needs a COMPLETE observation or explicit prior ceiling"
        )
    if lower >= upper:
        raise ValueError(
            "replay-wall observations are inconsistent: forfeit lower bound reaches "
            "or exceeds complete upper bound"
        )

    return ReplayWallCalibration(
        environment_key=next(iter(environments)),
        lower_cost_exclusive_seconds=lower,
        upper_cost_inclusive_seconds=upper,
        observation_count=len(observations),
        complete_count=complete_count,
        forfeit_count=forfeit_count,
    )


def replay_wall_forfeit_probability(
    calibration: ReplayWallCalibration,
    *,
    candidate_count: int,
    budget_seconds: float,
) -> ReplayWallRiskPoint:
    """Return an explicit uniform-interval risk estimate over the censored bounds.

    This is a planning assumption, not a learned truth. It answers: if the unknown
    average replay cost were uniformly distributed inside the evidence-consistent
    interval, how often would N candidates exceed the atomic replay wall?
    """

    if candidate_count < 1:
        raise ValueError("candidate_count must be positive")
    if budget_seconds <= 0 or not isfinite(budget_seconds):
        raise ValueError("budget_seconds must be finite and positive")

    threshold = budget_seconds / candidate_count
    lower = calibration.lower_cost_exclusive_seconds
    upper = calibration.upper_cost_inclusive_seconds
    if threshold >= upper:
        probability = 0.0
    elif threshold <= lower:
        probability = 1.0
    else:
        probability = (upper - threshold) / (upper - lower)

    return ReplayWallRiskPoint(
        candidate_count=candidate_count,
        budget_seconds=budget_seconds,
        forfeit_probability=max(0.0, min(1.0, probability)),
        threshold_seconds_per_candidate=threshold,
    )


def max_candidates_at_risk(
    calibration: ReplayWallCalibration,
    *,
    budget_seconds: float,
    max_candidates: int,
    target_forfeit_probability: float,
) -> ReplayWallPlan:
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if not 0.0 <= target_forfeit_probability <= 1.0:
        raise ValueError("target_forfeit_probability must be between 0 and 1")

    accepted = 0
    accepted_risk = 0.0
    for candidate_count in range(1, max_candidates + 1):
        point = replay_wall_forfeit_probability(
            calibration,
            candidate_count=candidate_count,
            budget_seconds=budget_seconds,
        )
        if point.forfeit_probability <= target_forfeit_probability + 1e-12:
            accepted = candidate_count
            accepted_risk = point.forfeit_probability
        else:
            break

    if accepted < 1:
        raise ValueError("no positive candidate count satisfies replay-wall risk target")

    next_risk = None
    if accepted < max_candidates:
        next_risk = replay_wall_forfeit_probability(
            calibration,
            candidate_count=accepted + 1,
            budget_seconds=budget_seconds,
        ).forfeit_probability

    return ReplayWallPlan(
        environment_key=calibration.environment_key,
        budget_seconds=budget_seconds,
        target_forfeit_probability=target_forfeit_probability,
        max_candidates=accepted,
        risk_at_max_candidates=accepted_risk,
        next_candidate_risk=next_risk,
    )
