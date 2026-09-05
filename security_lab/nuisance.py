from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    values: Mapping[str, str]


@dataclass(frozen=True)
class NuisanceOutcome:
    candidate_id: str
    case_id: str
    success: bool
    score: float


@dataclass(frozen=True)
class NuisanceSensitivityReport:
    candidate_id: str
    case_count: int
    success_rate: float
    mean_score: float
    worst_score: float
    best_score: float
    score_range: float
    failed_case_ids: tuple[str, ...]
    fragile: bool


def build_sweep(space: Mapping[str, Sequence[str]]) -> tuple[SweepCase, ...]:
    names = tuple(sorted(space))
    if any(len(space[name]) == 0 for name in names):
        raise ValueError("every sweep dimension requires at least one value")
    cases = []
    for index, values in enumerate(product(*(space[name] for name in names))):
        cases.append(
            SweepCase(
                f"case-{index:05d}",
                dict(zip(names, values, strict=True)),
            )
        )
    return tuple(cases)


def analyze_nuisance_sensitivity(
    outcomes: Sequence[NuisanceOutcome],
    *,
    minimum_success_rate: float = 1.0,
    maximum_score_range: float | None = None,
) -> NuisanceSensitivityReport:
    if not outcomes:
        raise ValueError("nuisance analysis requires at least one outcome")
    if not 0.0 <= minimum_success_rate <= 1.0:
        raise ValueError("minimum_success_rate must be between 0 and 1")
    if maximum_score_range is not None and maximum_score_range < 0:
        raise ValueError("maximum_score_range must be non-negative")

    candidate_ids = {item.candidate_id for item in outcomes}
    if len(candidate_ids) != 1:
        raise ValueError("nuisance outcomes must belong to one candidate")
    case_ids = [item.case_id for item in outcomes]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("nuisance case ids must be unique")

    scores = [item.score for item in outcomes]
    successes = sum(item.success for item in outcomes)
    success_rate = successes / len(outcomes)
    worst_score = min(scores)
    best_score = max(scores)
    score_range = best_score - worst_score
    fragile = success_rate < minimum_success_rate
    if maximum_score_range is not None and score_range > maximum_score_range:
        fragile = True

    return NuisanceSensitivityReport(
        candidate_id=next(iter(candidate_ids)),
        case_count=len(outcomes),
        success_rate=success_rate,
        mean_score=sum(scores) / len(scores),
        worst_score=worst_score,
        best_score=best_score,
        score_range=score_range,
        failed_case_ids=tuple(sorted(item.case_id for item in outcomes if not item.success)),
        fragile=fragile,
    )


def select_nuisance_stable_candidates(
    reports: Sequence[NuisanceSensitivityReport],
) -> tuple[str, ...]:
    by_id = {report.candidate_id: report for report in reports}
    if len(by_id) != len(reports):
        raise ValueError("nuisance reports require unique candidate ids")
    stable = [report for report in reports if not report.fragile]
    return tuple(
        report.candidate_id
        for report in sorted(
            stable,
            key=lambda item: (-item.success_rate, -item.worst_score, item.candidate_id),
        )
    )
