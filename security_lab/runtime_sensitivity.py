from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from .runtime_matrix import RuntimeVariant


@dataclass(frozen=True)
class RuntimeOutcome:
    candidate_id: str
    variant: RuntimeVariant
    score: float
    success: bool


@dataclass(frozen=True)
class RuntimeSensitivityReport:
    candidate_id: str
    runtime_count: int
    success_rate: float
    mean_score: float
    worst_score: float
    best_score: float
    score_range: float
    failed_runtime_keys: tuple[str, ...]
    fragile: bool


def analyze_runtime_sensitivity(
    outcomes: list[RuntimeOutcome],
    *,
    minimum_success_rate: float = 1.0,
    maximum_score_range: float | None = None,
) -> RuntimeSensitivityReport:
    if not outcomes:
        raise ValueError("runtime sensitivity requires at least one outcome")
    if not 0.0 <= minimum_success_rate <= 1.0:
        raise ValueError("minimum_success_rate must be within [0,1]")
    if maximum_score_range is not None and maximum_score_range < 0:
        raise ValueError("maximum_score_range must be non-negative")

    candidate_ids = {item.candidate_id for item in outcomes}
    if len(candidate_ids) != 1:
        raise ValueError("runtime sensitivity outcomes must belong to one candidate")

    runtime_keys = [runtime_variant_key(item.variant) for item in outcomes]
    if len(set(runtime_keys)) != len(runtime_keys):
        raise ValueError("runtime sensitivity requires unique runtime variants")

    scores = [item.score for item in outcomes]
    success_rate = sum(1 for item in outcomes if item.success) / len(outcomes)
    score_range = max(scores) - min(scores)
    failed = tuple(
        sorted(
            runtime_variant_key(item.variant)
            for item in outcomes
            if not item.success
        )
    )
    fragile = success_rate < minimum_success_rate
    if maximum_score_range is not None and score_range > maximum_score_range:
        fragile = True

    return RuntimeSensitivityReport(
        candidate_id=next(iter(candidate_ids)),
        runtime_count=len(outcomes),
        success_rate=success_rate,
        mean_score=mean(scores),
        worst_score=min(scores),
        best_score=max(scores),
        score_range=score_range,
        failed_runtime_keys=failed,
        fragile=fragile,
    )


def runtime_variant_key(variant: RuntimeVariant) -> str:
    return "|".join(
        (
            variant.model_id,
            variant.runtime_id,
            variant.compiler_id,
            variant.quantization,
        )
    )
