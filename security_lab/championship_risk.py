from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .competition_objective import CompetitionCandidateProfile, official_normalized_score
from .guardrail_scenarios import (
    CandidateScenarioSurvival,
    PrivateGuardrailScenario,
    ScenarioRobustPortfolioSelection,
    select_scenario_robust_portfolio,
)
from .replay_wall import (
    ReplayWallCalibration,
    ReplayWallPlan,
    max_candidates_at_risk,
    replay_wall_forfeit_probability,
)


@dataclass(frozen=True)
class RiskAwareChampionshipSelection:
    scenario_selection: ScenarioRobustPortfolioSelection
    replay_wall_plans: Mapping[str, ReplayWallPlan]
    selected_forfeit_probability_by_model: Mapping[str, float]
    atomic_adjusted_robust_raw_score_by_model: Mapping[str, float]
    atomic_adjusted_robust_normalized_score_by_model: Mapping[str, float]


def select_risk_aware_championship_portfolio(
    profiles: Sequence[CompetitionCandidateProfile],
    *,
    scenarios: Sequence[PrivateGuardrailScenario],
    survivals: Sequence[CandidateScenarioSurvival],
    runtime_budget_by_model: Mapping[str, float],
    replay_wall_calibration_by_model: Mapping[str, ReplayWallCalibration],
    target_forfeit_probability: float = 0.05,
    risk_aversion: float = 0.5,
    hard_candidate_limit_by_model: Mapping[str, int] | None = None,
) -> RiskAwareChampionshipSelection:
    """Plan a private-robust portfolio under an atomic replay-wall risk target.

    The wall calibration converts censored COMPLETE/FORFEIT observations into a
    candidate cap. The scenario selector then allocates only inside that cap.
    Finally, reported robust score is multiplied by the estimated probability the
    whole model phase completes, making the all-or-nothing loss visible.
    """

    if not 0.0 <= target_forfeit_probability <= 1.0:
        raise ValueError("target_forfeit_probability must be between 0 and 1")

    by_model: dict[str, list[CompetitionCandidateProfile]] = defaultdict(list)
    for profile in profiles:
        by_model[profile.model_id].append(profile)

    plans: dict[str, ReplayWallPlan] = {}
    caps: dict[str, int] = {}
    for model_id in sorted(by_model):
        if model_id not in runtime_budget_by_model:
            raise ValueError(f"missing runtime budget for model: {model_id}")
        if model_id not in replay_wall_calibration_by_model:
            raise ValueError(f"missing replay-wall calibration for model: {model_id}")

        available = len(by_model[model_id])
        hard_limit = available
        if hard_candidate_limit_by_model is not None and model_id in hard_candidate_limit_by_model:
            configured = hard_candidate_limit_by_model[model_id]
            if configured < 1:
                raise ValueError("hard candidate limits must be positive")
            hard_limit = min(hard_limit, configured)

        plan = max_candidates_at_risk(
            replay_wall_calibration_by_model[model_id],
            budget_seconds=float(runtime_budget_by_model[model_id]),
            max_candidates=hard_limit,
            target_forfeit_probability=target_forfeit_probability,
        )
        plans[model_id] = plan
        caps[model_id] = plan.max_candidates

    scenario_selection = select_scenario_robust_portfolio(
        profiles,
        scenarios=scenarios,
        survivals=survivals,
        runtime_budget_by_model=runtime_budget_by_model,
        risk_aversion=risk_aversion,
        max_candidates_by_model=caps,
    )

    selected_risk: dict[str, float] = {}
    atomic_raw: dict[str, float] = {}
    atomic_normalized: dict[str, float] = {}
    for model_id in sorted(scenario_selection.selected_by_model):
        selected_count = len(scenario_selection.selected_by_model[model_id])
        if selected_count == 0:
            forfeit_probability = 0.0
        else:
            forfeit_probability = replay_wall_forfeit_probability(
                replay_wall_calibration_by_model[model_id],
                candidate_count=selected_count,
                budget_seconds=float(runtime_budget_by_model[model_id]),
            ).forfeit_probability
        selected_risk[model_id] = forfeit_probability
        raw = (
            scenario_selection.robust_raw_score_by_model[model_id]
            * (1.0 - forfeit_probability)
        )
        atomic_raw[model_id] = raw
        atomic_normalized[model_id] = official_normalized_score(raw)

    return RiskAwareChampionshipSelection(
        scenario_selection=scenario_selection,
        replay_wall_plans=plans,
        selected_forfeit_probability_by_model=selected_risk,
        atomic_adjusted_robust_raw_score_by_model=atomic_raw,
        atomic_adjusted_robust_normalized_score_by_model=atomic_normalized,
    )
