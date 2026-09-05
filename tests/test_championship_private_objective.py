from security_lab.championship_io import run_championship_from_mapping
from security_lab.competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    SecurityPredicate,
    expected_private_raw_score,
    official_normalized_score,
    select_private_robust_portfolio,
)


def _finding(
    candidate_id: str,
    *,
    cell: str,
    severity: int,
    survival: float,
) -> CompetitionFindingSignal:
    return CompetitionFindingSignal(
        candidate_id=candidate_id,
        model_id="model",
        predicate=SecurityPredicate.CONFUSED_DEPUTY,
        severity=severity,
        cell_signature=cell,
        replay_success=True,
        private_survival_probability=survival,
    )


def _profile(
    candidate_id: str,
    findings: tuple[CompetitionFindingSignal, ...],
    *,
    runtime_seconds: float = 1.0,
) -> CompetitionCandidateProfile:
    return CompetitionCandidateProfile(
        candidate_id=candidate_id,
        family_id=f"family::{candidate_id}",
        model_id="model",
        runtime_seconds=runtime_seconds,
        findings=findings,
    )


def _environment() -> dict[str, object]:
    return {
        "model_id": "model",
        "runtime_id": "runtime",
        "quantization": "target",
        "evaluator_hash": "e" * 64,
        "runtime_version": "1.0.0",
        "compiler_id": "compiler",
    }


def _winning_candidate(candidate_id: str, score: float) -> dict[str, object]:
    trajectory_id = f"trajectory::{candidate_id}"
    probe_id = f"probe::{candidate_id}"
    return {
        "candidate_id": candidate_id,
        "family_id": f"family::{candidate_id}",
        "proxy_score": score,
        "throughput": 1.0,
        "failures": [False],
        "target_replay": {
            "trajectory": {
                "trajectory_id": trajectory_id,
                "probe_id": probe_id,
                "environment": _environment(),
                "steps": [{"kind": "replayed-step"}],
                "completed": True,
            },
            "observation": {
                "observation_id": f"observation::{candidate_id}",
                "probe_id": probe_id,
                "observable": "expected",
                "verdict": "SUPPORTED",
                "evidence_refs": [trajectory_id],
            },
        },
        "runtime_outcomes": [
            {
                "variant": {
                    "model_id": "model",
                    "runtime_id": "runtime",
                    "compiler_id": "compiler",
                    "quantization": "target",
                },
                "score": score,
                "success": True,
            }
        ],
    }


def test_official_normalization_matches_competition_formula() -> None:
    assert official_normalized_score(100_000.0) == 500.0
    assert official_normalized_score(200_000.0) == 1000.0
    assert official_normalized_score(400_000.0) == 1000.0


def test_expected_private_score_does_not_double_count_duplicate_cells() -> None:
    profile = _profile(
        "candidate",
        (
            _finding("candidate", cell="same", severity=1, survival=0.5),
            _finding("candidate", cell="same", severity=1, survival=0.5),
        ),
    )
    assert expected_private_raw_score([profile]) == 2.5


def test_selector_prefers_private_survival_over_nominal_severity() -> None:
    public_flashy = _profile(
        "public-flashy",
        (_finding("public-flashy", cell="cell-a", severity=5, survival=0.1),),
    )
    private_stable = _profile(
        "private-stable",
        (_finding("private-stable", cell="cell-b", severity=4, survival=0.9),),
    )

    result = select_private_robust_portfolio(
        [public_flashy, private_stable],
        runtime_budget_by_model={"model": 1.0},
    )
    assert result.selected_candidate_ids == ("private-stable",)


def test_championship_run_ignores_public_proxy_when_private_objective_disagrees() -> None:
    raw = {
        "winning_strategy": {
            "target_expectation": {
                "environment": _environment(),
                "required_observable": "expected",
            },
            "transfer_pairs": [
                {"proxy_score": 0.0, "target_score": 0.0},
                {"proxy_score": 10.0, "target_score": 10.0},
            ],
            "portfolio_limit": 0,
            "ridge_alpha": 0.0,
            "candidates": [
                _winning_candidate("public-flashy", 10.0),
                _winning_candidate("private-stable", 1.0),
            ],
        },
        "runtime_budget_by_model": {"model": 1.0},
        "competition_profiles": [
            {
                "candidate_id": "public-flashy",
                "family_id": "family::public-flashy",
                "model_id": "model",
                "runtime_seconds": 1.0,
                "findings": [
                    {
                        "predicate": "EXFILTRATION",
                        "severity": 5,
                        "cell_signature": "cell-a",
                        "replay_success": True,
                        "private_survival_probability": 0.1,
                    }
                ],
            },
            {
                "candidate_id": "private-stable",
                "family_id": "family::private-stable",
                "model_id": "model",
                "runtime_seconds": 1.0,
                "findings": [
                    {
                        "predicate": "CONFUSED_DEPUTY",
                        "severity": 4,
                        "cell_signature": "cell-b",
                        "replay_success": True,
                        "private_survival_probability": 0.9,
                    }
                ],
            },
        ],
    }

    result = run_championship_from_mapping(raw)
    assert result.competition_selection.selected_candidate_ids == ("private-stable",)
    assert result.decision.authority == "NONE"
    assert "public leaderboard score" in result.decision.rationale
