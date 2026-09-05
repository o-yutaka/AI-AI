from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite

from .competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    expected_private_raw_score,
    official_normalized_score,
)


@dataclass(frozen=True)
class PrivateGuardrailScenario:
    scenario_id: str
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id must be non-empty")
        if self.weight < 0 or not isfinite(self.weight):
            raise ValueError("scenario weight must be finite and non-negative")


@dataclass(frozen=True)
class CandidateScenarioSurvival:
    candidate_id: str
    scenario_id: str
    survival_probability: float

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.scenario_id:
            raise ValueError("candidate_id and scenario_id must be non-empty")
        if not 0.0 <= self.survival_probability <= 1.0:
            raise ValueError("survival_probability must be between 0 and 1")


@dataclass(frozen=True)
class ScenarioRobustPortfolioSelection:
    selected_candidate_ids: tuple[str, ...]
    selected_by_model: Mapping[str, tuple[str, ...]]
    scenario_raw_scores_by_model: Mapping[str, Mapping[str, float]]
    expected_raw_score_by_model: Mapping[str, float]
    worst_case_raw_score_by_model: Mapping[str, float]
    robust_raw_score_by_model: Mapping[str, float]
    robust_normalized_score_by_model: Mapping[str, float]
    runtime_seconds_by_model: Mapping[str, float]


def select_scenario_robust_portfolio(
    profiles: Sequence[CompetitionCandidateProfile],
    *,
    scenarios: Sequence[PrivateGuardrailScenario],
    survivals: Sequence[CandidateScenarioSurvival],
    runtime_budget_by_model: Mapping[str, float],
    risk_aversion: float = 0.5,
    max_candidates_by_model: Mapping[str, int] | None = None,
) -> ScenarioRobustPortfolioSelection:
    """Greedily maximize expected/worst-case private score per runtime second.

    `risk_aversion=0` uses weighted scenario expectation. `risk_aversion=1` uses
    the worst scenario only. Intermediate values blend both. Scenario survival
    multiplies the evidence-bound per-finding survival already present in a profile.
    """

    if not 0.0 <= risk_aversion <= 1.0:
        raise ValueError("risk_aversion must be between 0 and 1")
    if not profiles:
        return ScenarioRobustPortfolioSelection({}, {}, {}, {}, {}, {}, {}, {})  # type: ignore[arg-type]
    if len({profile.candidate_id for profile in profiles}) != len(profiles):
        raise ValueError("competition candidate IDs must be unique")

    scenario_map = _validated_scenarios(scenarios)
    survival_map = _validated_survivals(profiles, scenario_map, survivals)
    normalized_weights = _normalized_weights(scenario_map)

    by_model: dict[str, list[CompetitionCandidateProfile]] = defaultdict(list)
    for profile in profiles:
        by_model[profile.model_id].append(profile)

    selected_by_model: dict[str, tuple[str, ...]] = {}
    scenario_scores_by_model: dict[str, Mapping[str, float]] = {}
    expected_by_model: dict[str, float] = {}
    worst_by_model: dict[str, float] = {}
    robust_by_model: dict[str, float] = {}
    normalized_by_model: dict[str, float] = {}
    runtime_by_model: dict[str, float] = {}
    selected_ids: list[str] = []

    for model_id in sorted(by_model):
        if model_id not in runtime_budget_by_model:
            raise ValueError(f"missing runtime budget for model: {model_id}")
        budget = float(runtime_budget_by_model[model_id])
        if budget < 0 or not isfinite(budget):
            raise ValueError("runtime budgets must be finite and non-negative")
        cap = None if max_candidates_by_model is None else max_candidates_by_model.get(model_id)
        if cap is not None and cap < 1:
            raise ValueError("model candidate caps must be positive")

        selected: list[CompetitionCandidateProfile] = []
        remaining = sorted(by_model[model_id], key=lambda item: item.candidate_id)
        used_runtime = 0.0

        while remaining:
            if cap is not None and len(selected) >= cap:
                break
            current_robust = _portfolio_metrics(
                selected,
                scenario_map,
                normalized_weights,
                survival_map,
                risk_aversion,
            )[2]
            options: list[tuple[float, float, float, str, CompetitionCandidateProfile]] = []
            for candidate in remaining:
                if used_runtime + candidate.runtime_seconds > budget + 1e-12:
                    continue
                _, _, next_robust, _ = _portfolio_metrics(
                    [*selected, candidate],
                    scenario_map,
                    normalized_weights,
                    survival_map,
                    risk_aversion,
                )
                marginal = next_robust - current_robust
                if marginal <= 0:
                    continue
                utility = marginal / candidate.runtime_seconds
                options.append(
                    (-utility, -marginal, candidate.runtime_seconds, candidate.candidate_id, candidate)
                )
            if not options:
                break
            chosen = sorted(options, key=lambda item: item[:4])[0][4]
            selected.append(chosen)
            used_runtime += chosen.runtime_seconds
            remaining = [item for item in remaining if item.candidate_id != chosen.candidate_id]

        expected, worst, robust, scenario_scores = _portfolio_metrics(
            selected,
            scenario_map,
            normalized_weights,
            survival_map,
            risk_aversion,
        )
        ids = tuple(item.candidate_id for item in selected)
        selected_by_model[model_id] = ids
        scenario_scores_by_model[model_id] = scenario_scores
        expected_by_model[model_id] = expected
        worst_by_model[model_id] = worst
        robust_by_model[model_id] = robust
        normalized_by_model[model_id] = official_normalized_score(robust)
        runtime_by_model[model_id] = used_runtime
        selected_ids.extend(ids)

    return ScenarioRobustPortfolioSelection(
        selected_candidate_ids=tuple(selected_ids),
        selected_by_model=selected_by_model,
        scenario_raw_scores_by_model=scenario_scores_by_model,
        expected_raw_score_by_model=expected_by_model,
        worst_case_raw_score_by_model=worst_by_model,
        robust_raw_score_by_model=robust_by_model,
        robust_normalized_score_by_model=normalized_by_model,
        runtime_seconds_by_model=runtime_by_model,
    )


def _validated_scenarios(
    scenarios: Sequence[PrivateGuardrailScenario],
) -> dict[str, PrivateGuardrailScenario]:
    if not scenarios:
        raise ValueError("at least one private guardrail scenario is required")
    result = {item.scenario_id: item for item in scenarios}
    if len(result) != len(scenarios):
        raise ValueError("scenario ids must be unique")
    if sum(item.weight for item in scenarios) <= 0:
        raise ValueError("at least one scenario weight must be positive")
    return result


def _normalized_weights(
    scenarios: Mapping[str, PrivateGuardrailScenario],
) -> dict[str, float]:
    total = sum(item.weight for item in scenarios.values())
    return {key: scenarios[key].weight / total for key in sorted(scenarios)}


def _validated_survivals(
    profiles: Sequence[CompetitionCandidateProfile],
    scenarios: Mapping[str, PrivateGuardrailScenario],
    survivals: Sequence[CandidateScenarioSurvival],
) -> dict[tuple[str, str], float]:
    profile_ids = {item.candidate_id for item in profiles}
    result: dict[tuple[str, str], float] = {}
    for item in survivals:
        if item.candidate_id not in profile_ids:
            raise ValueError(f"scenario survival references unknown candidate: {item.candidate_id}")
        if item.scenario_id not in scenarios:
            raise ValueError(f"scenario survival references unknown scenario: {item.scenario_id}")
        key = (item.candidate_id, item.scenario_id)
        if key in result:
            raise ValueError(f"duplicate scenario survival: {item.candidate_id}/{item.scenario_id}")
        result[key] = item.survival_probability

    missing = sorted(
        f"{candidate_id}/{scenario_id}"
        for candidate_id in profile_ids
        for scenario_id in scenarios
        if (candidate_id, scenario_id) not in result
    )
    if missing:
        raise ValueError("missing scenario survival evidence: " + ",".join(missing))
    return result


def _portfolio_metrics(
    profiles: Sequence[CompetitionCandidateProfile],
    scenarios: Mapping[str, PrivateGuardrailScenario],
    normalized_weights: Mapping[str, float],
    survival_map: Mapping[tuple[str, str], float],
    risk_aversion: float,
) -> tuple[float, float, float, dict[str, float]]:
    scenario_scores: dict[str, float] = {}
    for scenario_id in sorted(scenarios):
        adjusted = [
            _scenario_profile(profile, scenario_id, survival_map)
            for profile in profiles
        ]
        scenario_scores[scenario_id] = expected_private_raw_score(adjusted)

    expected = sum(
        normalized_weights[scenario_id] * score
        for scenario_id, score in scenario_scores.items()
    )
    worst = min(scenario_scores.values()) if scenario_scores else 0.0
    robust = (1.0 - risk_aversion) * expected + risk_aversion * worst
    return expected, worst, robust, scenario_scores


def _scenario_profile(
    profile: CompetitionCandidateProfile,
    scenario_id: str,
    survival_map: Mapping[tuple[str, str], float],
) -> CompetitionCandidateProfile:
    multiplier = survival_map[(profile.candidate_id, scenario_id)]
    findings = tuple(
        CompetitionFindingSignal(
            candidate_id=finding.candidate_id,
            model_id=finding.model_id,
            predicate=finding.predicate,
            severity=finding.severity,
            cell_signature=finding.cell_signature,
            replay_success=finding.replay_success,
            private_survival_probability=(
                finding.private_survival_probability * multiplier
            ),
        )
        for finding in profile.findings
    )
    return CompetitionCandidateProfile(
        candidate_id=profile.candidate_id,
        family_id=profile.family_id,
        model_id=profile.model_id,
        runtime_seconds=profile.runtime_seconds,
        findings=findings,
    )
