from __future__ import annotations

from dataclasses import dataclass

from .models import FamilyResult, Split
from .robustness import RobustnessEnvelope


@dataclass(frozen=True)
class JudgeThresholds:
    minimum_support_score: float = 0.5
    minimum_success_rate: float = 0.8
    minimum_worst_score: float = 0.0
    minimum_margin: float | None = None


@dataclass(frozen=True)
class JudgeVerdict:
    verdict: str
    reason_codes: tuple[str, ...]


def judge_family(
    family: FamilyResult,
    robustness: RobustnessEnvelope,
    *,
    split: Split,
    thresholds: JudgeThresholds = JudgeThresholds(),
) -> JudgeVerdict:
    reasons: list[str] = []
    if split not in {Split.HELD_OUT, Split.ADVERSARIAL_HELD_OUT}:
        reasons.append("not_held_out")
    if family.eliminated or family.support_score < thresholds.minimum_support_score:
        reasons.append("family_support_below_gate")
    if robustness.success_rate < thresholds.minimum_success_rate:
        reasons.append("robustness_success_rate_below_gate")
    if robustness.worst_score < thresholds.minimum_worst_score:
        reasons.append("worst_score_below_gate")
    if thresholds.minimum_margin is not None:
        if robustness.minimum_margin is None:
            reasons.append("margin_missing")
        elif robustness.minimum_margin < thresholds.minimum_margin:
            reasons.append("minimum_margin_below_gate")
    if reasons:
        return JudgeVerdict("REJECTED", tuple(sorted(reasons)))
    return JudgeVerdict("VERIFIED_FOR_RESEARCH", ("held_out_research_gate_passed",))
