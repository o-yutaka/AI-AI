from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .models import EnvironmentIdentity, Observation, ProbeVerdict, Trajectory
from .replay import ReplayResult
from .runtime_matrix import RuntimeVariant
from .runtime_sensitivity import RuntimeOutcome
from .target_gate import TargetReplayExpectation
from .transfer import TransferPair
from .winning_pipeline import (
    WinningCandidateEvidence,
    WinningStrategyResult,
    rank_winning_portfolio,
)


def rank_winning_portfolio_from_mapping(raw: Mapping[str, Any]) -> WinningStrategyResult:
    expectation_raw = _mapping(raw["target_expectation"])
    expectation = TargetReplayExpectation(
        environment=_environment(_mapping(expectation_raw["environment"])),
        required_verdict=ProbeVerdict(
            str(expectation_raw.get("required_verdict", ProbeVerdict.SUPPORTED.value))
        ),
        required_observable=_optional_str(expectation_raw.get("required_observable")),
        require_completed=bool(expectation_raw.get("require_completed", True)),
    )
    candidates = [
        _candidate_evidence(_mapping(item))
        for item in _sequence(raw["candidates"])
    ]
    transfer_pairs = [
        TransferPair(
            proxy_score=float(_mapping(item)["proxy_score"]),
            target_score=float(_mapping(item)["target_score"]),
        )
        for item in _sequence(raw["transfer_pairs"])
    ]
    return rank_winning_portfolio(
        candidates,
        transfer_pairs=transfer_pairs,
        target_expectation=expectation,
        portfolio_limit=int(raw["portfolio_limit"]),
        ridge_alpha=float(raw.get("ridge_alpha", 1.0)),
        residual_multiplier=float(raw.get("residual_multiplier", 1.0)),
        minimum_runtime_success_rate=float(
            raw.get("minimum_runtime_success_rate", 1.0)
        ),
        maximum_runtime_score_range=_optional_float(
            raw.get("maximum_runtime_score_range")
        ),
        correlation_penalty=float(raw.get("correlation_penalty", 1.0)),
    )


def winning_strategy_result_payload(result: WinningStrategyResult) -> dict[str, Any]:
    return {
        "calibration": {
            "slope": result.calibration.slope,
            "intercept": result.calibration.intercept,
            "alpha": result.calibration.alpha,
            "residual_mae": result.calibration.residual_mae,
            "residual_max": result.calibration.residual_max,
            "sample_count": result.calibration.sample_count,
        },
        "selected_candidate_ids": list(result.selected_candidate_ids),
        "assessments": [
            {
                "candidate_id": item.candidate_id,
                "predicted_target_score": item.predicted_target_score,
                "conservative_target_score": item.conservative_target_score,
                "eligible": item.eligible,
                "reason_codes": list(item.reason_codes),
                "target_gate_passed": item.target_gate.passed,
                "runtime_fragile": item.runtime_sensitivity.fragile,
                "runtime_success_rate": item.runtime_sensitivity.success_rate,
                "runtime_score_range": item.runtime_sensitivity.score_range,
            }
            for item in result.assessments
        ],
    }


def _candidate_evidence(raw: Mapping[str, Any]) -> WinningCandidateEvidence:
    candidate_id = str(raw["candidate_id"])
    replay_raw = _mapping(raw["target_replay"])
    trajectory_raw = _mapping(replay_raw["trajectory"])
    observation_raw = _mapping(replay_raw["observation"])
    trajectory = Trajectory(
        trajectory_id=str(trajectory_raw["trajectory_id"]),
        probe_id=str(trajectory_raw["probe_id"]),
        environment=_environment(_mapping(trajectory_raw["environment"])),
        steps=tuple(
            dict(_mapping(step))
            for step in _sequence(trajectory_raw.get("steps", ()))
        ),
        token_count=int(trajectory_raw.get("token_count", 0)),
        latency_ms=float(trajectory_raw.get("latency_ms", 0.0)),
        completed=bool(trajectory_raw.get("completed", True)),
    )
    observation = Observation(
        observation_id=str(observation_raw["observation_id"]),
        probe_id=str(observation_raw["probe_id"]),
        observable=str(observation_raw["observable"]),
        verdict=ProbeVerdict(str(observation_raw["verdict"])),
        metrics={
            str(key): float(value)
            for key, value in _mapping(observation_raw.get("metrics", {})).items()
        },
        evidence_refs=tuple(
            str(item) for item in _sequence(observation_raw.get("evidence_refs", ()))
        ),
    )
    runtime_outcomes = tuple(
        _runtime_outcome(candidate_id, _mapping(item))
        for item in _sequence(raw["runtime_outcomes"])
    )
    return WinningCandidateEvidence(
        candidate_id=candidate_id,
        family_id=str(raw["family_id"]),
        proxy_score=float(raw["proxy_score"]),
        target_replay=ReplayResult(observation, trajectory),
        runtime_outcomes=runtime_outcomes,
        failures=tuple(bool(item) for item in _sequence(raw["failures"])),
        throughput=float(raw["throughput"]),
    )


def _runtime_outcome(candidate_id: str, raw: Mapping[str, Any]) -> RuntimeOutcome:
    variant_raw = _mapping(raw["variant"])
    return RuntimeOutcome(
        candidate_id=str(raw.get("candidate_id", candidate_id)),
        variant=RuntimeVariant(
            model_id=str(variant_raw["model_id"]),
            runtime_id=str(variant_raw["runtime_id"]),
            compiler_id=str(variant_raw["compiler_id"]),
            quantization=str(variant_raw["quantization"]),
        ),
        score=float(raw["score"]),
        success=bool(raw["success"]),
    )


def _environment(raw: Mapping[str, Any]) -> EnvironmentIdentity:
    return EnvironmentIdentity(
        model_id=str(raw["model_id"]),
        runtime_id=str(raw["runtime_id"]),
        quantization=_optional_str(raw.get("quantization")),
        tool_surface_hash=_optional_str(raw.get("tool_surface_hash")),
        evaluator_hash=_optional_str(raw.get("evaluator_hash")),
        model_revision=_optional_str(raw.get("model_revision")),
        runtime_version=_optional_str(raw.get("runtime_version")),
        tokenizer_revision=_optional_str(raw.get("tokenizer_revision")),
        compiler_id=_optional_str(raw.get("compiler_id")),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected JSON object")
    return value


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("expected JSON array")
    return value


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
