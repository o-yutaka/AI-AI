from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .failure_correlation import (
    FailureProfile,
    build_failure_correlation_graph,
    select_correlation_diverse_portfolio,
)
from .minimum_trace import (
    MinimumWinningTrace,
    TraceEvaluation,
    TraceSteps,
    minimize_winning_trace,
)
from .portfolio import CandidateProfile
from .replay import ReplayResult
from .runtime_sensitivity import (
    RuntimeOutcome,
    RuntimeSensitivityReport,
    analyze_runtime_sensitivity,
)
from .target_gate import (
    TargetReplayExpectation,
    TargetReplayVerdict,
    evaluate_target_replay,
)
from .transfer import RidgeTransferEstimate, TransferPair, fit_ridge_transfer


@dataclass(frozen=True)
class WinningCandidateEvidence:
    candidate_id: str
    family_id: str
    proxy_score: float
    target_replay: ReplayResult
    runtime_outcomes: tuple[RuntimeOutcome, ...]
    failures: tuple[bool, ...]
    throughput: float


@dataclass(frozen=True)
class WinningCandidateAssessment:
    candidate_id: str
    predicted_target_score: float
    conservative_target_score: float
    target_gate: TargetReplayVerdict
    runtime_sensitivity: RuntimeSensitivityReport
    minimum_trace: MinimumWinningTrace | None
    eligible: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class WinningStrategyResult:
    calibration: RidgeTransferEstimate
    assessments: tuple[WinningCandidateAssessment, ...]
    selected_candidate_ids: tuple[str, ...]


CandidateTraceEvaluator = Callable[[str, TraceSteps], TraceEvaluation]


def rank_winning_portfolio(
    evidence: list[WinningCandidateEvidence],
    *,
    transfer_pairs: list[TransferPair],
    target_expectation: TargetReplayExpectation,
    portfolio_limit: int,
    ridge_alpha: float = 1.0,
    residual_multiplier: float = 1.0,
    minimum_runtime_success_rate: float = 1.0,
    maximum_runtime_score_range: float | None = None,
    correlation_penalty: float = 1.0,
    trace_evaluator: CandidateTraceEvaluator | None = None,
    minimum_prefix_steps: int = 0,
) -> WinningStrategyResult:
    """Rank candidates through the lab's transferable winning-strategy gates."""

    if portfolio_limit < 0:
        raise ValueError("portfolio_limit must be non-negative")
    if len({item.candidate_id for item in evidence}) != len(evidence):
        raise ValueError("winning candidate IDs must be unique")

    calibration = fit_ridge_transfer(transfer_pairs, alpha=ridge_alpha)
    assessments: list[WinningCandidateAssessment] = []
    profiles: list[CandidateProfile] = []
    failure_profiles: list[FailureProfile] = []

    for item in sorted(evidence, key=lambda current: current.candidate_id):
        _validate_runtime_candidate_binding(item)
        target_gate = evaluate_target_replay(target_expectation, item.target_replay)
        runtime_report = analyze_runtime_sensitivity(
            list(item.runtime_outcomes),
            minimum_success_rate=minimum_runtime_success_rate,
            maximum_score_range=maximum_runtime_score_range,
        )
        predicted = calibration.predict(item.proxy_score)
        conservative = calibration.conservative_lower_bound(
            item.proxy_score,
            residual_multiplier=residual_multiplier,
        )

        reasons = list(target_gate.reason_codes)
        if runtime_report.fragile:
            reasons.append("runtime_fragile")
        if item.throughput < 0:
            reasons.append("negative_throughput")

        minimum_trace: MinimumWinningTrace | None = None
        if trace_evaluator is not None and not reasons:
            try:
                minimum_trace = minimize_winning_trace(
                    item.target_replay.trajectory,
                    lambda steps: trace_evaluator(item.candidate_id, steps),
                    minimum_prefix_steps=minimum_prefix_steps,
                )
            except ValueError:
                reasons.append("minimum_trace_gate_failed")

        eligible = not reasons
        assessment = WinningCandidateAssessment(
            candidate_id=item.candidate_id,
            predicted_target_score=predicted,
            conservative_target_score=conservative,
            target_gate=target_gate,
            runtime_sensitivity=runtime_report,
            minimum_trace=minimum_trace,
            eligible=eligible,
            reason_codes=tuple(sorted(reasons)),
        )
        assessments.append(assessment)

        if eligible:
            profiles.append(
                CandidateProfile(
                    candidate_id=item.candidate_id,
                    family_id=item.family_id,
                    expected_score=conservative,
                    survival_probability=runtime_report.success_rate,
                    throughput=item.throughput,
                    failure_cluster=item.candidate_id,
                )
            )
            failure_profiles.append(FailureProfile(item.candidate_id, item.failures))

    selected: tuple[str, ...] = ()
    if profiles and portfolio_limit > 0:
        graph = build_failure_correlation_graph(failure_profiles)
        selected = tuple(
            item.candidate_id
            for item in select_correlation_diverse_portfolio(
                profiles,
                graph,
                portfolio_limit,
                correlation_penalty=correlation_penalty,
            )
        )

    return WinningStrategyResult(
        calibration=calibration,
        assessments=tuple(assessments),
        selected_candidate_ids=selected,
    )


def _validate_runtime_candidate_binding(item: WinningCandidateEvidence) -> None:
    if not item.runtime_outcomes:
        raise ValueError(
            f"candidate {item.candidate_id} requires at least one runtime outcome"
        )
    mismatched = sorted(
        outcome.candidate_id
        for outcome in item.runtime_outcomes
        if outcome.candidate_id != item.candidate_id
    )
    if mismatched:
        raise ValueError(
            f"runtime outcomes are not bound to candidate {item.candidate_id}"
        )
