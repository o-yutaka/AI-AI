from __future__ import annotations

from collections import defaultdict

from .models import FamilyResult, Hypothesis, Observation, ProbeVerdict


class HypothesisGraph:
    def __init__(self, hypotheses: list[Hypothesis]) -> None:
        self._hypotheses = {item.hypothesis_id: item for item in hypotheses}

    def get(self, hypothesis_id: str) -> Hypothesis:
        return self._hypotheses[hypothesis_id]

    def by_family(self) -> dict[str, list[Hypothesis]]:
        grouped: dict[str, list[Hypothesis]] = defaultdict(list)
        for hypothesis in self._hypotheses.values():
            grouped[hypothesis.family_id].append(hypothesis)
        return {
            key: sorted(value, key=lambda item: item.hypothesis_id)
            for key, value in grouped.items()
        }


def score_families(
    graph: HypothesisGraph,
    observations: list[Observation],
    eliminate_below: float = 0.25,
    minimum_samples: int = 2,
) -> list[FamilyResult]:
    by_hypothesis: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        hypothesis_id = observation.probe_id.split("::", 1)[0]
        by_hypothesis[hypothesis_id].append(observation)

    results: list[FamilyResult] = []
    for family_id, hypotheses in graph.by_family().items():
        family_observations: list[Observation] = []
        for hypothesis in hypotheses:
            family_observations.extend(by_hypothesis.get(hypothesis.hypothesis_id, []))
        weighted = sum(_verdict_weight(item.verdict) for item in family_observations)
        sample_count = len(family_observations)
        if sample_count == 0:
            support_score = 0.5
        else:
            support_score = max(0.0, min(1.0, 0.5 + weighted / (2 * sample_count)))
        eliminated = sample_count >= minimum_samples and support_score < eliminate_below
        if sample_count < minimum_samples:
            reason = "insufficient_evidence"
        elif eliminated:
            reason = "below_support_gate"
        else:
            reason = "survives"
        results.append(
            FamilyResult(family_id, support_score, sample_count, eliminated, reason)
        )
    return sorted(results, key=lambda item: (-item.support_score, item.family_id))


def _verdict_weight(verdict: ProbeVerdict) -> float:
    return {
        ProbeVerdict.SUPPORTED: 1.0,
        ProbeVerdict.REFUTED: -1.0,
        ProbeVerdict.INCONCLUSIVE: 0.0,
        ProbeVerdict.BLOCKED: -0.25,
    }[verdict]
