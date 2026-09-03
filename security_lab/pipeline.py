from __future__ import annotations

from dataclasses import dataclass

from .hypothesis import HypothesisGraph, score_families
from .judge import JudgeThresholds, JudgeVerdict, judge_family
from .models import FamilyResult, Hypothesis, Observation, Split
from .robustness import RobustnessEnvelope


@dataclass(frozen=True)
class ResearchDecision:
    family: FamilyResult
    judge: JudgeVerdict


def rank_and_judge(
    hypotheses: list[Hypothesis],
    observations: list[Observation],
    robustness_by_family: dict[str, RobustnessEnvelope],
    *,
    split: Split,
    thresholds: JudgeThresholds | None = None,
) -> list[ResearchDecision]:
    graph = HypothesisGraph(hypotheses)
    families = score_families(graph, observations)
    decisions: list[ResearchDecision] = []
    for family in families:
        envelope = robustness_by_family.get(family.family_id)
        if envelope is None:
            decisions.append(
                ResearchDecision(
                    family=family,
                    judge=JudgeVerdict("BLOCKED", ("robustness_evidence_missing",)),
                )
            )
            continue
        decisions.append(
            ResearchDecision(
                family=family,
                judge=judge_family(
                    family,
                    envelope,
                    split=split,
                    thresholds=thresholds,
                ),
            )
        )
    return decisions
