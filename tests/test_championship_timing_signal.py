from security_lab.championship_io import run_championship_from_mapping


def _environment() -> dict[str, object]:
    return {
        "model_id": "gpt_oss",
        "runtime_id": "runtime",
        "quantization": "target",
        "evaluator_hash": "e" * 64,
        "runtime_version": "1.0.0",
        "compiler_id": "compiler",
    }


def _candidate(candidate_id: str, proxy_score: float) -> dict[str, object]:
    probe_id = f"probe::{candidate_id}"
    trajectory_id = f"trajectory::{candidate_id}"
    return {
        "candidate_id": candidate_id,
        "family_id": f"family::{candidate_id}",
        "proxy_score": proxy_score,
        "throughput": 1.0,
        "failures": [False],
        "target_replay": {
            "trajectory": {
                "trajectory_id": trajectory_id,
                "probe_id": probe_id,
                "environment": _environment(),
                "steps": [{"kind": "recorded"}],
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
                    "model_id": "gpt_oss",
                    "runtime_id": "runtime",
                    "compiler_id": "compiler",
                    "quantization": "target",
                },
                "score": proxy_score,
                "success": True,
            }
        ],
    }


def test_timing_calibration_can_drive_private_survival_selection() -> None:
    environment_key = "gpt_oss::runtime::compiler::target"
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
                _candidate("public-flashy", 10.0),
                _candidate("timing-stable", 2.0),
            ],
        },
        "runtime_budget_by_model": {"gpt_oss": 1.0},
        "max_candidates_per_model": 1,
        "timing_calibrations": {
            "private-path": {
                "minimum_separation_s": 1.0,
                "samples": [
                    {"sample_id": "s1", "outcome": "SUCCESS", "elapsed_seconds": 1.0, "environment_key": environment_key},
                    {"sample_id": "s2", "outcome": "SUCCESS", "elapsed_seconds": 1.1, "environment_key": environment_key},
                    {"sample_id": "s3", "outcome": "SUCCESS", "elapsed_seconds": 0.9, "environment_key": environment_key},
                    {"sample_id": "b1", "outcome": "BLOCKED", "elapsed_seconds": 8.0, "environment_key": environment_key},
                    {"sample_id": "b2", "outcome": "BLOCKED", "elapsed_seconds": 8.1, "environment_key": environment_key},
                    {"sample_id": "b3", "outcome": "BLOCKED", "elapsed_seconds": 7.9, "environment_key": environment_key}
                ]
            }
        },
        "competition_profiles": [
            {
                "candidate_id": "public-flashy",
                "family_id": "family::public-flashy",
                "model_id": "gpt_oss",
                "runtime_seconds": 1.0,
                "findings": [
                    {
                        "predicate": "EXFILTRATION",
                        "severity": 5,
                        "cell_signature": "cell-public",
                        "replay_success": True,
                        "private_survival_probability": 0.2
                    }
                ]
            },
            {
                "candidate_id": "timing-stable",
                "family_id": "family::timing-stable",
                "model_id": "gpt_oss",
                "runtime_seconds": 1.0,
                "findings": [
                    {
                        "predicate": "CONFUSED_DEPUTY",
                        "severity": 4,
                        "cell_signature": "cell-stable",
                        "replay_success": True,
                        "timing_signal": {
                            "calibration_id": "private-path",
                            "elapsed_seconds": [1.0, 1.2, 1.1],
                            "environment_key": environment_key
                        }
                    }
                ]
            }
        ]
    }

    result = run_championship_from_mapping(raw)
    assert result.competition_selection.selected_candidate_ids == ("timing-stable",)


def test_finding_cannot_double_source_private_survival() -> None:
    raw = {
        "winning_strategy": {
            "target_expectation": {"environment": _environment()},
            "transfer_pairs": [
                {"proxy_score": 0.0, "target_score": 0.0},
                {"proxy_score": 1.0, "target_score": 1.0},
            ],
            "portfolio_limit": 0,
            "candidates": [_candidate("candidate", 1.0)],
        },
        "runtime_budget_by_model": {"gpt_oss": 1.0},
        "timing_calibrations": {},
        "competition_profiles": [
            {
                "candidate_id": "candidate",
                "family_id": "family::candidate",
                "model_id": "gpt_oss",
                "runtime_seconds": 1.0,
                "findings": [
                    {
                        "predicate": "CONFUSED_DEPUTY",
                        "severity": 3,
                        "cell_signature": "cell",
                        "replay_success": True,
                        "private_survival_probability": 0.5,
                        "timing_signal": {
                            "calibration_id": "missing",
                            "elapsed_seconds": [1.0],
                            "environment_key": "env"
                        }
                    }
                ]
            }
        ]
    }

    try:
        run_championship_from_mapping(raw)
    except ValueError as exc:
        assert "either private_survival_probability or timing_signal" in str(exc)
    else:
        raise AssertionError("dual private-survival sources should fail closed")
