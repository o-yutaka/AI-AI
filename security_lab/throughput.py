from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThroughputEstimate:
    candidate_seconds: float
    budget_seconds: float
    candidates_completed: int
    expected_successes: float


def estimate_throughput(
    *,
    candidate_seconds: float,
    budget_seconds: float,
    success_probability: float,
) -> ThroughputEstimate:
    if candidate_seconds <= 0 or budget_seconds < 0:
        raise ValueError("invalid timing inputs")
    if not 0 <= success_probability <= 1:
        raise ValueError("success_probability must be within [0,1]")
    completed = int(budget_seconds // candidate_seconds)
    return ThroughputEstimate(
        candidate_seconds,
        budget_seconds,
        completed,
        completed * success_probability,
    )
