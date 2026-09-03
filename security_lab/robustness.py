from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class RobustnessSample:
    condition_id: str
    score: float
    success: bool
    margin: float | None = None


@dataclass(frozen=True)
class RobustnessEnvelope:
    sample_count: int
    success_rate: float
    mean_score: float
    worst_score: float
    minimum_margin: float | None
    failed_conditions: tuple[str, ...]


def build_robustness_envelope(samples: list[RobustnessSample]) -> RobustnessEnvelope:
    if not samples:
        raise ValueError("robustness envelope requires at least one sample")
    margins = [item.margin for item in samples if item.margin is not None]
    failed = tuple(sorted(item.condition_id for item in samples if not item.success))
    return RobustnessEnvelope(
        sample_count=len(samples),
        success_rate=sum(1 for item in samples if item.success) / len(samples),
        mean_score=mean(item.score for item in samples),
        worst_score=min(item.score for item in samples),
        minimum_margin=min(margins) if margins else None,
        failed_conditions=failed,
    )
