from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from research_bundle.models import KnowledgeMaterial, ResearchDecisionRecord

from .championship_risk import (
    RiskAwareChampionshipSelection,
    select_risk_aware_championship_portfolio,
)
from .competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    SecurityPredicate,
)
from .guardrail_scenarios import CandidateScenarioSurvival, PrivateGuardrailScenario
from .replay_wall import (
    ReplayWallCalibration,
    ReplayWallObservation,
    ReplayWallOutcome,
    calibrate_replay_wall,
)
from .sdk_runtime_contract import (
    championship_replay_budgets,
    kaggle_host_faq_contract,
    runtime_contract_from_mapping,
)
from .timing_signal import TimingCalibration
from .timing_signal_io import (
    resolve_private_survival_probability,
    timing_calibrations_from_mapping,
)
from .winning_io import rank_winning_portfolio_from_mapping, winning_strategy_result_payload
from .winning_pipeline import WinningStrategyResult


@dataclass(frozen=True)
class RiskAwareChampionshipRun:
    winning_strategy: WinningStrategyResult
    risk_selection: RiskAwareChampionshipSelection
    decision: ResearchDecisionRecord
    knowledge_materials: tuple[KnowledgeMaterial, ...]


def run_risk_championship_from_mapping(raw: Mapping[str, Any]) -> RiskAwareChampionshipRun:
    winning_strategy = rank_winning_portfolio_from_mapping(_mapping(raw["winning_strategy"]))
    timing_raw = raw.get("timing_calibrations")
    timing_calibrations = timing_calibrations_from_mapping(
        None if timing_raw is None else _mapping(timing_raw)
    )
    profiles = [
        _competition_profile(_mapping(item), timing_calibrations)
        for item in _sequence(raw["competition_profiles"])
    ]
    runtime_budget_by_model = _resolve_runtime_budgets(raw, profiles)

    assessments = {
        assessment.candidate_id: assessment for assessment in winning_strategy.assessments
    }
    unknown = sorted(
        profile.candidate_id for profile in profiles if profile.candidate_id not in assessments
    )
    if unknown:
        raise ValueError(
            "competition profiles are not bound to winning-strategy assessments: "
            + ",".join(unknown)
        )
    eligible_profiles = [
        profile
        for profile in profiles
        if assessments[profile.candidate_id].eligible
    ]
    eligible_ids = {profile.candidate_id for profile in eligible_profiles}

    scenarios = tuple(
        PrivateGuardrailScenario(
            scenario_id=str(_mapping(item)["scenario_id"]),
            weight=float(_mapping(item).get("weight", 1.0)),
        )
        for item in _sequence(raw["guardrail_scenarios"])
    )
    survivals = tuple(
        CandidateScenarioSurvival(
            candidate_id=str(_mapping(item)["candidate_id"]),
            scenario_id=str(_mapping(item)["scenario_id"]),
            survival_probability=float(_mapping(item)["survival_probability"]),
        )
        for item in _sequence(raw["scenario_survivals"])
        if str(_mapping(item)["candidate_id"]) in eligible_ids
    )
    calibrations = _replay_wall_calibrations(raw, eligible_profiles)

    policy = _mapping(raw.get("championship_risk_policy", {}))
    hard_limits_raw = policy.get("hard_candidate_limit_by_model")
    hard_limits = None
    if hard_limits_raw is not None:
        hard_limits = {
            str(model_id): int(value) for model_id, value in _mapping(hard_limits_raw).items()
        }

    risk_selection = select_risk_aware_championship_portfolio(
        eligible_profiles,
        scenarios=scenarios,
        survivals=survivals,
        runtime_budget_by_model=runtime_budget_by_model,
        replay_wall_calibration_by_model=calibrations,
        target_forfeit_probability=float(policy.get("target_forfeit_probability", 0.05)),
        risk_aversion=float(policy.get("risk_aversion", 0.5)),
        hard_candidate_limit_by_model=hard_limits,
    )

    selected = set(risk_selection.scenario_selection.selected_candidate_ids)
    considered = sorted(profile.candidate_id for profile in profiles)
    decision = ResearchDecisionRecord(
        decision_id="research-decision::championship-risk-oracle-v3",
        stage="private_scenario_and_replay_wall_selection",
        candidates_considered=considered,
        selected=sorted(selected),
        rejected=sorted(
            candidate_id for candidate_id in considered if candidate_id not in selected
        ),
        rationale=(
            "filtered by exact winning-strategy gates, capped each model by evidence-bound atomic "
            "replay-wall risk, then maximized expected/worst-case private scenario score per "
            "runtime second; public leaderboard score is not an optimization input"
        ),
        evidence_refs=[],
        budget_units_spent=0.0,
    )
    materials = tuple(
        _risk_material(model_id, risk_selection)
        for model_id in sorted(risk_selection.scenario_selection.selected_by_model)
    )
    return RiskAwareChampionshipRun(
        winning_strategy=winning_strategy,
        risk_selection=risk_selection,
        decision=decision,
        knowledge_materials=materials,
    )


def risk_championship_result_payload(result: RiskAwareChampionshipRun) -> dict[str, Any]:
    selection = result.risk_selection
    scenario = selection.scenario_selection
    return {
        "winning_strategy": winning_strategy_result_payload(result.winning_strategy),
        "championship_risk": {
            "selected_candidate_ids": list(scenario.selected_candidate_ids),
            "selected_by_model": {
                model_id: list(candidate_ids)
                for model_id, candidate_ids in scenario.selected_by_model.items()
            },
            "scenario_raw_scores_by_model": {
                model_id: dict(scores)
                for model_id, scores in scenario.scenario_raw_scores_by_model.items()
            },
            "expected_raw_score_by_model": dict(scenario.expected_raw_score_by_model),
            "worst_case_raw_score_by_model": dict(scenario.worst_case_raw_score_by_model),
            "robust_raw_score_by_model": dict(scenario.robust_raw_score_by_model),
            "atomic_adjusted_robust_raw_score_by_model": dict(
                selection.atomic_adjusted_robust_raw_score_by_model
            ),
            "atomic_adjusted_robust_normalized_score_by_model": dict(
                selection.atomic_adjusted_robust_normalized_score_by_model
            ),
            "runtime_seconds_by_model": dict(scenario.runtime_seconds_by_model),
            "selected_forfeit_probability_by_model": dict(
                selection.selected_forfeit_probability_by_model
            ),
            "replay_wall_plans": {
                model_id: {
                    "environment_key": plan.environment_key,
                    "budget_seconds": plan.budget_seconds,
                    "target_forfeit_probability": plan.target_forfeit_probability,
                    "max_candidates": plan.max_candidates,
                    "risk_at_max_candidates": plan.risk_at_max_candidates,
                    "next_candidate_risk": plan.next_candidate_risk,
                }
                for model_id, plan in selection.replay_wall_plans.items()
            },
        },
        "research_decision": result.decision.model_dump(mode="json"),
        "knowledge_materials": [
            item.model_dump(mode="json") for item in result.knowledge_materials
        ],
    }


def _risk_material(
    model_id: str,
    selection: RiskAwareChampionshipSelection,
) -> KnowledgeMaterial:
    scenario = selection.scenario_selection
    plan = selection.replay_wall_plans[model_id]
    return KnowledgeMaterial(
        material_id=f"championship-risk::{model_id}",
        kind="SEARCH_DECISION",
        subject_ref=model_id,
        statement=(
            "championship portfolio selected under private guardrail scenarios and an atomic "
            "replay-wall risk cap"
        ),
        evidence_refs=[],
        metrics={
            "expected_private_raw_score": scenario.expected_raw_score_by_model[model_id],
            "worst_case_private_raw_score": scenario.worst_case_raw_score_by_model[model_id],
            "robust_private_raw_score": scenario.robust_raw_score_by_model[model_id],
            "atomic_adjusted_robust_raw_score": (
                selection.atomic_adjusted_robust_raw_score_by_model[model_id]
            ),
            "selected_forfeit_probability": (
                selection.selected_forfeit_probability_by_model[model_id]
            ),
            "replay_wall_candidate_cap": float(plan.max_candidates),
        },
        tags=["championship", "private_scenarios", "atomic_replay_wall", "public_score_absent"],
        confidence=0.7,
    )


def _replay_wall_calibrations(
    raw: Mapping[str, Any],
    profiles: Sequence[CompetitionCandidateProfile],
) -> dict[str, ReplayWallCalibration]:
    wall_raw = _mapping(raw["replay_wall_by_model"])
    model_ids = {profile.model_id for profile in profiles}
    result: dict[str, ReplayWallCalibration] = {}
    for model_id in sorted(model_ids):
        if model_id not in wall_raw:
            raise ValueError(f"missing replay_wall_by_model entry: {model_id}")
        spec = _mapping(wall_raw[model_id])
        environment_key = str(spec["environment_key"])
        observations = [
            ReplayWallObservation(
                environment_key=environment_key,
                candidate_count=int(_mapping(item)["candidate_count"]),
                budget_seconds=float(_mapping(item)["budget_seconds"]),
                outcome=ReplayWallOutcome(str(_mapping(item)["outcome"])),
            )
            for item in _sequence(spec["observations"])
        ]
        ceiling_raw = spec.get("prior_cost_ceiling_seconds")
        result[model_id] = calibrate_replay_wall(
            observations,
            prior_cost_floor_seconds=float(spec.get("prior_cost_floor_seconds", 0.0)),
            prior_cost_ceiling_seconds=(
                None if ceiling_raw is None else float(ceiling_raw)
            ),
        )
    return result


def _resolve_runtime_budgets(
    raw: Mapping[str, Any],
    profiles: Sequence[CompetitionCandidateProfile],
) -> dict[str, float]:
    explicit = raw.get("runtime_budget_by_model")
    contract_raw = raw.get("runtime_contract")
    profile_name = raw.get("runtime_contract_profile")
    provided = sum(value is not None for value in (explicit, contract_raw, profile_name))
    if provided > 1:
        raise ValueError(
            "provide either runtime_budget_by_model or runtime_contract, "
            "or runtime_contract_profile; not more than one"
        )
    if explicit is not None:
        return {str(model_id): float(value) for model_id, value in _mapping(explicit).items()}
    if contract_raw is not None:
        contract = runtime_contract_from_mapping(dict(_mapping(contract_raw)))
    elif profile_name is not None:
        if str(profile_name) != "kaggle-host-faq-9000-v1":
            raise ValueError(f"unknown runtime contract profile: {profile_name}")
        contract = kaggle_host_faq_contract()
    else:
        raise ValueError("championship risk run requires runtime budget information")

    policy = _mapping(raw.get("runtime_policy", {}))
    return championship_replay_budgets(
        contract,
        model_ids=tuple(profile.model_id for profile in profiles),
        reserve_seconds=float(policy.get("reserve_seconds", 0.0)),
        reserve_fraction=float(policy.get("reserve_fraction", 0.0)),
    )


def _competition_profile(
    raw: Mapping[str, Any],
    timing_calibrations: Mapping[str, TimingCalibration],
) -> CompetitionCandidateProfile:
    candidate_id = str(raw["candidate_id"])
    model_id = str(raw["model_id"])
    findings = tuple(
        _finding(candidate_id, model_id, _mapping(item), timing_calibrations)
        for item in _sequence(raw.get("findings", ()))
    )
    return CompetitionCandidateProfile(
        candidate_id=candidate_id,
        family_id=str(raw["family_id"]),
        model_id=model_id,
        runtime_seconds=float(raw["runtime_seconds"]),
        findings=findings,
    )


def _finding(
    candidate_id: str,
    model_id: str,
    raw: Mapping[str, Any],
    timing_calibrations: Mapping[str, TimingCalibration],
) -> CompetitionFindingSignal:
    return CompetitionFindingSignal(
        candidate_id=str(raw.get("candidate_id", candidate_id)),
        model_id=str(raw.get("model_id", model_id)),
        predicate=SecurityPredicate(str(raw["predicate"])),
        severity=int(raw["severity"]),
        cell_signature=str(raw["cell_signature"]),
        replay_success=bool(raw["replay_success"]),
        private_survival_probability=resolve_private_survival_probability(raw, timing_calibrations),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected JSON object")
    return value


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("expected JSON array")
    return value
