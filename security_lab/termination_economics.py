from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class TerminationRuntimeSample:
    candidate_id: str
    runtime_key: str
    successful_action_preserved: bool
    post_success_tokens: int
    post_success_latency_s: float
    eog_margin: float | None = None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id must be non-empty")
        if not self.runtime_key:
            raise ValueError("runtime_key must be non-empty")
        if self.post_success_tokens < 0:
            raise ValueError("post_success_tokens must be non-negative")
        if self.post_success_latency_s < 0:
            raise ValueError("post_success_latency_s must be non-negative")


@dataclass(frozen=True)
class TerminationCandidateReport:
    candidate_id: str
    runtime_count: int
    all_successful_actions_preserved: bool
    mean_post_success_tokens: float
    worst_post_success_tokens: int
    mean_post_success_latency_s: float
    worst_post_success_latency_s: float
    minimum_eog_margin: float | None
    effective_mean_cost_s: float
    effective_worst_cost_s: float
    eligible: bool
    rejection_reasons: tuple[str, ...]


@dataclass(frozen=True)
class TerminationEconomicsResult:
    selected_candidate_id: str | None
    ranked_candidate_ids: tuple[str, ...]
    reports: tuple[TerminationCandidateReport, ...]


def analyze_termination_economics(
    samples: tuple[TerminationRuntimeSample, ...],
    *,
    token_seconds: float = 0.0,
    minimum_eog_margin: float | None = None,
    require_all_runtimes: bool = True,
) -> TerminationEconomicsResult:
    """Rank benchmark candidates by cost *after* the scored action has succeeded.

    The scored action must remain intact. This layer only measures waste after success:
    extra generated tokens, latency, and optional end-of-generation margin. It does not
    construct attack payloads or change the security predicate itself.
    """

    if token_seconds < 0:
        raise ValueError("token_seconds must be non-negative")
    if not samples:
        raise ValueError("termination economics requires runtime samples")

    grouped: dict[str, list[TerminationRuntimeSample]] = defaultdict(list)
    for sample in samples:
        grouped[sample.candidate_id].append(sample)

    reports: list[TerminationCandidateReport] = []
    for candidate_id in sorted(grouped):
        candidate_samples = grouped[candidate_id]
        runtime_keys = [sample.runtime_key for sample in candidate_samples]
        if len(runtime_keys) != len(set(runtime_keys)):
            raise ValueError(
                f"duplicate runtime sample for candidate: {candidate_id}"
            )

        preserved = [sample.successful_action_preserved for sample in candidate_samples]
        margins = [
            sample.eog_margin
            for sample in candidate_samples
            if sample.eog_margin is not None
        ]
        minimum_margin = min(margins) if margins else None
        reasons: list[str] = []
        if require_all_runtimes and not all(preserved):
            reasons.append("successful_action_not_preserved_on_all_runtimes")
        elif not any(preserved):
            reasons.append("successful_action_not_preserved")
        if minimum_eog_margin is not None:
            if minimum_margin is None:
                reasons.append("eog_margin_missing")
            elif minimum_margin < minimum_eog_margin:
                reasons.append("eog_margin_below_gate")

        costs = [
            sample.post_success_latency_s
            + token_seconds * sample.post_success_tokens
            for sample in candidate_samples
        ]
        reports.append(
            TerminationCandidateReport(
                candidate_id=candidate_id,
                runtime_count=len(candidate_samples),
                all_successful_actions_preserved=all(preserved),
                mean_post_success_tokens=mean(
                    sample.post_success_tokens for sample in candidate_samples
                ),
                worst_post_success_tokens=max(
                    sample.post_success_tokens for sample in candidate_samples
                ),
                mean_post_success_latency_s=mean(
                    sample.post_success_latency_s for sample in candidate_samples
                ),
                worst_post_success_latency_s=max(
                    sample.post_success_latency_s for sample in candidate_samples
                ),
                minimum_eog_margin=minimum_margin,
                effective_mean_cost_s=mean(costs),
                effective_worst_cost_s=max(costs),
                eligible=not reasons,
                rejection_reasons=tuple(sorted(reasons)),
            )
        )

    eligible = [report for report in reports if report.eligible]
    ranked = sorted(
        eligible,
        key=lambda report: (
            report.effective_worst_cost_s,
            report.effective_mean_cost_s,
            -(
                report.minimum_eog_margin
                if report.minimum_eog_margin is not None
                else float("-inf")
            ),
            report.candidate_id,
        ),
    )
    return TerminationEconomicsResult(
        selected_candidate_id=ranked[0].candidate_id if ranked else None,
        ranked_candidate_ids=tuple(report.candidate_id for report in ranked),
        reports=tuple(reports),
    )


def post_success_capacity_gain(
    *,
    baseline_cost_s: float,
    optimized_cost_s: float,
    replay_budget_s: float,
) -> int:
    """Estimate extra replay slots from post-success cost reduction alone."""

    if baseline_cost_s <= 0 or optimized_cost_s <= 0:
        raise ValueError("termination costs must be positive")
    if replay_budget_s < 0:
        raise ValueError("replay_budget_s must be non-negative")
    baseline_capacity = int(replay_budget_s // baseline_cost_s)
    optimized_capacity = int(replay_budget_s // optimized_cost_s)
    return optimized_capacity - baseline_capacity
