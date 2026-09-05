from __future__ import annotations

import pytest

from security_lab.championship_risk import select_risk_aware_championship_portfolio
from security_lab.competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    SecurityPredicate,
)
from security_lab.guardrail_scenarios import (
    CandidateScenarioSurvival,
    PrivateGuardrailScenario,
    select_scenario_robust_portfolio,
)
from security_lab.replay_wall import (
    ReplayWallObservation,
    ReplayWallOutcome,
    calibrate_replay_wall,
    max_candidates_at_risk,
    replay_wall_forfeit_probability,
)


def _profile(candidate_id: str, cell: str, *, runtime: float = 1.0) -> CompetitionCandidateProfile:
    return CompetitionCandidateProfile(
        candidate_id=candidate_id,
        family_id=f"family::{candidate_id}",
        model_id="model-a",
        runtime_seconds=runtime,
        findings=(
            CompetitionFindingSignal(
                candidate_id=candidate_id,
                model_id="model-a",
                predicate=SecurityPredicate.CONFUSED_DEPUTY,
                severity=5,
                cell_signature=cell,
                replay_success=True,
                private_survival_probability=1.0,
            ),
        ),
    )


def test_censored_replay_wall_recovers_interval_and_zero_risk_cap() -> None:
    calibration = calibrate_replay_wall(
        [
            ReplayWallObservation("exact-env", 400, 9000.0, ReplayWallOutcome.COMPLETE),
            ReplayWallObservation("exact-env", 800, 9000.0, ReplayWallOutcome.FORFEIT),
        ]
    )

    assert calibration.lower_cost_exclusive_seconds == pytest.approx(11.25)
    assert calibration.upper_cost_inclusive_seconds == pytest.approx(22.5)
    assert replay_wall_forfeit_probability(
        calibration, candidate_count=400, budget_seconds=9000.0
    ).forfeit_probability == 0.0
    assert replay_wall_forfeit_probability(
        calibration, candidate_count=800, budget_seconds=9000.0
    ).forfeit_probability == 1.0

    plan = max_candidates_at_risk(
        calibration,
        budget_seconds=9000.0,
        max_candidates=1000,
        target_forfeit_probability=0.0,
    )
    assert plan.max_candidates == 400
    assert plan.risk_at_max_candidates == 0.0
    assert plan.next_candidate_risk is not None
    assert plan.next_candidate_risk > 0.0


def test_replay_wall_risk_is_monotonic_and_mixed_environments_fail_closed() -> None:
    calibration = calibrate_replay_wall(
        [
            ReplayWallObservation("env", 4, 100.0, ReplayWallOutcome.COMPLETE),
            ReplayWallObservation("env", 8, 100.0, ReplayWallOutcome.FORFEIT),
        ]
    )
    risks = [
        replay_wall_forfeit_probability(
            calibration, candidate_count=count, budget_seconds=100.0
        ).forfeit_probability
        for count in range(1, 9)
    ]
    assert risks == sorted(risks)

    with pytest.raises(ValueError, match="one exact environment_key"):
        calibrate_replay_wall(
            [
                ReplayWallObservation("env-a", 4, 100.0, ReplayWallOutcome.COMPLETE),
                ReplayWallObservation("env-b", 8, 100.0, ReplayWallOutcome.FORFEIT),
            ]
        )


def test_scenario_beam_search_keeps_complementary_candidates() -> None:
    profiles = [_profile("a", "cell-a"), _profile("b", "cell-b"), _profile("c", "cell-c")]
    scenarios = [PrivateGuardrailScenario("guard-a"), PrivateGuardrailScenario("guard-b")]
    survivals = [
        CandidateScenarioSurvival("a", "guard-a", 1.0),
        CandidateScenarioSurvival("a", "guard-b", 0.0),
        CandidateScenarioSurvival("b", "guard-a", 0.0),
        CandidateScenarioSurvival("b", "guard-b", 1.0),
        CandidateScenarioSurvival("c", "guard-a", 0.6),
        CandidateScenarioSurvival("c", "guard-b", 0.6),
    ]

    result = select_scenario_robust_portfolio(
        profiles,
        scenarios=scenarios,
        survivals=survivals,
        runtime_budget_by_model={"model-a": 2.0},
        risk_aversion=1.0,
        max_candidates_by_model={"model-a": 2},
        beam_width=3,
    )

    assert result.selected_by_model["model-a"] == ("a", "b")
    assert result.worst_case_raw_score_by_model["model-a"] == pytest.approx(18.0)
    assert result.robust_raw_score_by_model["model-a"] == pytest.approx(18.0)


def test_missing_scenario_survival_fails_closed() -> None:
    with pytest.raises(ValueError, match="missing scenario survival evidence"):
        select_scenario_robust_portfolio(
            [_profile("a", "cell-a")],
            scenarios=[PrivateGuardrailScenario("guard-a"), PrivateGuardrailScenario("guard-b")],
            survivals=[CandidateScenarioSurvival("a", "guard-a", 1.0)],
            runtime_budget_by_model={"model-a": 10.0},
        )


def test_risk_aware_selector_applies_atomic_wall_before_scenario_search() -> None:
    profiles = [_profile("a", "cell-a"), _profile("b", "cell-b")]
    calibration = calibrate_replay_wall(
        [
            ReplayWallObservation("exact-env", 1, 10.0, ReplayWallOutcome.COMPLETE),
            ReplayWallObservation("exact-env", 2, 10.0, ReplayWallOutcome.FORFEIT),
        ]
    )
    scenarios = [PrivateGuardrailScenario("guard-a"), PrivateGuardrailScenario("guard-b")]
    survivals = [
        CandidateScenarioSurvival("a", "guard-a", 1.0),
        CandidateScenarioSurvival("a", "guard-b", 0.8),
        CandidateScenarioSurvival("b", "guard-a", 0.8),
        CandidateScenarioSurvival("b", "guard-b", 1.0),
    ]

    result = select_risk_aware_championship_portfolio(
        profiles,
        scenarios=scenarios,
        survivals=survivals,
        runtime_budget_by_model={"model-a": 10.0},
        replay_wall_calibration_by_model={"model-a": calibration},
        target_forfeit_probability=0.0,
        risk_aversion=0.5,
    )

    assert result.replay_wall_plans["model-a"].max_candidates == 1
    assert len(result.scenario_selection.selected_by_model["model-a"]) == 1
    assert result.selected_forfeit_probability_by_model["model-a"] == 0.0
    assert result.atomic_adjusted_robust_raw_score_by_model["model-a"] == pytest.approx(
        result.scenario_selection.robust_raw_score_by_model["model-a"]
    )
