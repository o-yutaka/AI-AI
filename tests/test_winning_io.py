from security_lab.winning_io import (
    rank_winning_portfolio_from_mapping,
    winning_strategy_result_payload,
)


def _environment(version: str = "1.0.0") -> dict[str, object]:
    return {
        "model_id": "model",
        "runtime_id": "runtime",
        "quantization": "target",
        "evaluator_hash": "e" * 64,
        "runtime_version": version,
        "compiler_id": "compiler",
    }


def _candidate(candidate_id: str, score: float, failures: list[bool]) -> dict[str, object]:
    trajectory_id = f"trajectory::{candidate_id}"
    probe_id = f"probe::{candidate_id}"
    return {
        "candidate_id": candidate_id,
        "family_id": f"family::{candidate_id}",
        "proxy_score": score,
        "throughput": 1.0,
        "failures": failures,
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


def test_json_adapter_ranks_recorded_evidence_deterministically() -> None:
    raw = {
        "target_expectation": {
            "environment": _environment(),
            "required_observable": "expected",
        },
        "transfer_pairs": [
            {"proxy_score": 0.0, "target_score": 0.0},
            {"proxy_score": 10.0, "target_score": 10.0},
        ],
        "portfolio_limit": 2,
        "ridge_alpha": 0.0,
        "correlation_penalty": 1.0,
        "candidates": [
            _candidate("a", 10.0, [True, True, False, False]),
            _candidate("b", 9.0, [True, True, False, False]),
            _candidate("c", 8.0, [False, False, True, True]),
        ],
    }
    result = rank_winning_portfolio_from_mapping(raw)
    payload = winning_strategy_result_payload(result)

    assert result.selected_candidate_ids == ("a", "c")
    assert payload["selected_candidate_ids"] == ["a", "c"]
    assert all(item["eligible"] for item in payload["assessments"])


def test_json_adapter_preserves_target_runtime_gate() -> None:
    raw = {
        "target_expectation": {"environment": _environment("2.0.0")},
        "transfer_pairs": [
            {"proxy_score": 0.0, "target_score": 0.0},
            {"proxy_score": 1.0, "target_score": 1.0},
        ],
        "portfolio_limit": 1,
        "ridge_alpha": 0.0,
        "candidates": [_candidate("a", 1.0, [False])],
    }
    result = rank_winning_portfolio_from_mapping(raw)
    assert result.selected_candidate_ids == ()
    assert result.assessments[0].reason_codes == ("environment_identity_mismatch",)
