from dataclasses import replace

import pytest

from security_lab.championship_io import run_championship_from_mapping
from security_lab.sdk_runtime_contract import (
    CandidateShape,
    CompetitionRuntimeContract,
    ContractEvidenceTier,
    ModelPhaseBudgets,
    RuntimePhase,
    SdkRunSignature,
    championship_replay_budgets,
    kaggle_host_faq_contract,
    plan_runtime_capacity,
    validate_candidate_shapes,
)


def _environment() -> dict[str, object]:
    return {
        "model_id": "gpt_oss",
        "runtime_id": "runtime",
        "quantization": "target",
        "evaluator_hash": "e" * 64,
        "runtime_version": "1.0.0",
        "compiler_id": "compiler",
    }


def _winning_candidate(candidate_id: str) -> dict[str, object]:
    trajectory_id = f"trajectory::{candidate_id}"
    probe_id = f"probe::{candidate_id}"
    return {
        "candidate_id": candidate_id,
        "family_id": "family",
        "proxy_score": 1.0,
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
                "score": 1.0,
                "success": True,
            }
        ],
    }


def test_host_faq_profile_encodes_host_clarification_without_guessing_sdk_details() -> None:
    contract = kaggle_host_faq_contract()
    assert contract.phase_budget("gpt_oss", RuntimePhase.ATTACK_GENERATION) == 9_000.0
    assert contract.phase_budget("gemma", RuntimePhase.PRIVATE_REPLAY) == 9_000.0
    assert contract.global_runtime_limit_s == 54_000.0
    assert contract.max_candidates == 2_000
    assert contract.max_messages_per_candidate == 32
    assert contract.max_tool_hops_per_interact == 8
    assert contract.run_signature is SdkRunSignature.UNKNOWN
    assert contract.max_user_message_chars is None


def test_contract_fingerprint_changes_when_runtime_truth_changes() -> None:
    base = kaggle_host_faq_contract()
    changed = replace(
        base,
        model_phase_budgets={
            "gpt_oss": ModelPhaseBudgets(18_000.0, 18_000.0, 18_000.0),
            "gemma": ModelPhaseBudgets(18_000.0, 18_000.0, 18_000.0),
        },
    )
    assert base.fingerprint() != changed.fingerprint()


def test_custom_sdk_observation_can_enforce_signature_and_message_limit() -> None:
    contract = CompetitionRuntimeContract(
        contract_id="sdk-observed",
        evidence_tier=ContractEvidenceTier.SDK_OBSERVED,
        source_ref="local-sdk-inspection",
        sdk_version="3.1.2",
        run_signature=SdkRunSignature.ENV_AND_RUN_CONFIG,
        model_phase_budgets={"gpt_oss": ModelPhaseBudgets(9_000, 9_000, 9_000)},
        max_user_message_chars=2_000,
        max_messages_per_candidate=32,
    )
    assert contract.run_signature is SdkRunSignature.ENV_AND_RUN_CONFIG
    validate_candidate_shapes(contract, (CandidateShape((2_000,)),))
    with pytest.raises(ValueError, match="character limit"):
        validate_candidate_shapes(contract, (CandidateShape((2_001,)),))


def test_candidate_and_tool_limits_fail_closed() -> None:
    contract = kaggle_host_faq_contract()
    with pytest.raises(ValueError, match="message count"):
        validate_candidate_shapes(contract, (CandidateShape((1,) * 33),))
    with pytest.raises(ValueError, match="tool hops"):
        validate_candidate_shapes(contract, (CandidateShape((1,), (9,)),))
    with pytest.raises(ValueError, match="candidate count"):
        validate_candidate_shapes(contract, tuple(CandidateShape((1,)) for _ in range(2_001)))


def test_runtime_capacity_reserves_headroom_and_respects_candidate_cap() -> None:
    contract = kaggle_host_faq_contract()
    plan = plan_runtime_capacity(
        contract,
        model_id="gpt_oss",
        phase=RuntimePhase.PRIVATE_REPLAY,
        expected_seconds_per_candidate=3.0,
        reserve_fraction=0.10,
    )
    assert plan.gross_budget_s == 9_000.0
    assert plan.usable_budget_s == 8_100.0
    assert plan.max_candidates_by_time == 2_700
    assert plan.max_candidates_after_contract_cap == 2_000


def test_championship_replay_budget_uses_smaller_phase_and_reserve() -> None:
    contract = CompetitionRuntimeContract(
        contract_id="asymmetric",
        evidence_tier=ContractEvidenceTier.USER_SUPPLIED,
        source_ref="test",
        model_phase_budgets={"gpt_oss": ModelPhaseBudgets(9_000, 9_000, 8_000)},
    )
    assert championship_replay_budgets(
        contract,
        model_ids=("gpt_oss",),
        reserve_seconds=500,
    ) == {"gpt_oss": 7_500.0}


def test_unknown_model_budget_fails_closed() -> None:
    with pytest.raises(ValueError, match="no budget for model"):
        kaggle_host_faq_contract().phase_budget("future-model", RuntimePhase.PRIVATE_REPLAY)


def test_championship_can_derive_budget_from_versioned_runtime_contract() -> None:
    raw = {
        "winning_strategy": {
            "target_expectation": {
                "environment": _environment(),
                "required_observable": "expected",
            },
            "transfer_pairs": [
                {"proxy_score": 0.0, "target_score": 0.0},
                {"proxy_score": 1.0, "target_score": 1.0},
            ],
            "portfolio_limit": 0,
            "ridge_alpha": 0.0,
            "candidates": [_winning_candidate("candidate")],
        },
        "runtime_contract": {
            "contract_id": "host-like",
            "evidence_tier": "HOST_OFFICIAL",
            "source_ref": "test-host-faq",
            "model_phase_budgets": {
                "gpt_oss": {
                    "attack_generation_s": 9000,
                    "public_replay_s": 9000,
                    "private_replay_s": 9000
                }
            },
            "max_candidates": 2000,
            "max_messages_per_candidate": 32,
            "max_tool_hops_per_interact": 8
        },
        "runtime_policy": {"reserve_seconds": 1000},
        "competition_profiles": [
            {
                "candidate_id": "candidate",
                "family_id": "family",
                "model_id": "gpt_oss",
                "runtime_seconds": 8000,
                "findings": [
                    {
                        "predicate": "CONFUSED_DEPUTY",
                        "severity": 3,
                        "cell_signature": "cell-a",
                        "replay_success": True,
                        "private_survival_probability": 1.0
                    }
                ]
            }
        ]
    }
    result = run_championship_from_mapping(raw)
    assert result.competition_selection.selected_candidate_ids == ("candidate",)
    assert result.competition_selection.runtime_seconds_by_model == {"gpt_oss": 8000.0}


def test_championship_rejects_ambiguous_dual_budget_sources() -> None:
    raw = {
        "winning_strategy": {
            "target_expectation": {"environment": _environment()},
            "transfer_pairs": [
                {"proxy_score": 0.0, "target_score": 0.0},
                {"proxy_score": 1.0, "target_score": 1.0},
            ],
            "portfolio_limit": 0,
            "candidates": [_winning_candidate("candidate")],
        },
        "competition_profiles": [],
        "runtime_budget_by_model": {"gpt_oss": 9000},
        "runtime_contract": {
            "contract_id": "duplicate",
            "evidence_tier": "USER_SUPPLIED",
            "source_ref": "test",
            "model_phase_budgets": {
                "gpt_oss": {
                    "attack_generation_s": 9000,
                    "public_replay_s": 9000,
                    "private_replay_s": 9000
                }
            }
        }
    }
    with pytest.raises(ValueError, match="either runtime_budget_by_model or runtime_contract"):
        run_championship_from_mapping(raw)
