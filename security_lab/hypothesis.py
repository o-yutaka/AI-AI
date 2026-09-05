from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from .belief import HypothesisBelief, update_belief
from .models import FamilyResult, Hypothesis, Observation, ProbeVerdict


class HypothesisRelationType(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    SUPERSEDES = "supersedes"
    SAME_FAILURE_FAMILY = "same_failure_family"
    SAME_MECHANISM_FAMILY = "same_mechanism_family"


@dataclass(frozen=True)
class HypothesisRelation:
    source_id: str
    target_id: str
    relation: HypothesisRelationType
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class HypothesisEvidenceState:
    hypothesis_id: str
    prior: float
    posterior: float
    support_count: int
    refutation_count: int
    inconclusive_count: int
    blocked_count: int
    last_observation_id: str | None


class HypothesisGraph:
    def __init__(
        self,
        hypotheses: list[Hypothesis],
        relations: list[HypothesisRelation] | None = None,
    ) -> None:
        self._hypotheses = {item.hypothesis_id: item for item in hypotheses}
        if len(self._hypotheses) != len(hypotheses):
            raise ValueError("hypothesis ids must be unique")
        self._relations = tuple(relations or ())
        for relation in self._relations:
            if relation.source_id not in self._hypotheses:
                raise ValueError(f"unknown relation source: {relation.source_id}")
            if relation.target_id not in self._hypotheses:
                raise ValueError(f"unknown relation target: {relation.target_id}")
            if relation.source_id == relation.target_id:
                raise ValueError("hypothesis relation cannot self-reference")

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

    def relations_from(
        self,
        hypothesis_id: str,
        relation: HypothesisRelationType | None = None,
    ) -> tuple[HypothesisRelation, ...]:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(hypothesis_id)
        return tuple(
            item
            for item in self._relations
            if item.source_id == hypothesis_id
            and (relation is None or item.relation is relation)
        )

    def relations_to(
        self,
        hypothesis_id: str,
        relation: HypothesisRelationType | None = None,
    ) -> tuple[HypothesisRelation, ...]:
        if hypothesis_id not in self._hypotheses:
            raise KeyError(hypothesis_id)
        return tuple(
            item
            for item in self._relations
            if item.target_id == hypothesis_id
            and (relation is None or item.relation is relation)
        )

    @property
    def relations(self) -> tuple[HypothesisRelation, ...]:
        return self._relations


def summarize_hypothesis_evidence(
    graph: HypothesisGraph,
    observations: list[Observation],
) -> dict[str, HypothesisEvidenceState]:
    by_hypothesis: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        hypothesis_id = observation.probe_id.split("::", 1)[0]
        if hypothesis_id in graph._hypotheses:
            by_hypothesis[hypothesis_id].append(observation)

    states: dict[str, HypothesisEvidenceState] = {}
    for hypothesis_id in sorted(graph._hypotheses):
        hypothesis = graph.get(hypothesis_id)
        belief = HypothesisBelief(hypothesis_id, hypothesis.prior)
        support_count = 0
        refutation_count = 0
        inconclusive_count = 0
        blocked_count = 0
        ordered = by_hypothesis.get(hypothesis_id, [])
        for observation in ordered:
            belief = update_belief(belief, observation)
            if observation.verdict is ProbeVerdict.SUPPORTED:
                support_count += 1
            elif observation.verdict is ProbeVerdict.REFUTED:
                refutation_count += 1
            elif observation.verdict is ProbeVerdict.INCONCLUSIVE:
                inconclusive_count += 1
            elif observation.verdict is ProbeVerdict.BLOCKED:
                blocked_count += 1
        states[hypothesis_id] = HypothesisEvidenceState(
            hypothesis_id=hypothesis_id,
            prior=hypothesis.prior,
            posterior=belief.probability,
            support_count=support_count,
            refutation_count=refutation_count,
            inconclusive_count=inconclusive_count,
            blocked_count=blocked_count,
            last_observation_id=ordered[-1].observation_id if ordered else None,
        )
    return states


def score_families(
    graph: HypothesisGraph,
    observations: list[Observation],
    eliminate_below: float = 0.25,
    minimum_samples: int = 2,
) -> list[FamilyResult]:
    by_hypothesis: dict[str, list[Observation]] = defaultdict(list)
    for observation in observations:
        by_hypothesis[observation.probe_id.split("::", 1)[0]].append(observation)

    results: list[FamilyResult] = []
    for family_id, hypotheses in graph.by_family().items():
        family_observations: list[Observation] = []
        for hypothesis in hypotheses:
            family_observations.extend(
                by_hypothesis.get(hypothesis.hypothesis_id, [])
            )
        weighted = sum(
            _verdict_weight(item.verdict) for item in family_observations
        )
        sample_count = len(family_observations)
        if sample_count == 0:
            support_score = 0.5
        else:
            support_score = max(
                0.0,
                min(1.0, 0.5 + weighted / (2 * sample_count)),
            )
        eliminated = (
            sample_count >= minimum_samples
            and support_score < eliminate_below
        )
        if sample_count < minimum_samples:
            reason = "insufficient_evidence"
        elif eliminated:
            reason = "below_support_gate"
        else:
            reason = "survives"
        results.append(
            FamilyResult(
                family_id,
                support_score,
                sample_count,
                eliminated,
                reason,
            )
        )
    return sorted(results, key=lambda item: (-item.support_score, item.family_id))


def _verdict_weight(verdict: ProbeVerdict) -> float:
    return {
        ProbeVerdict.SUPPORTED: 1.0,
        ProbeVerdict.REFUTED: -1.0,
        ProbeVerdict.INCONCLUSIVE: 0.0,
        ProbeVerdict.BLOCKED: -0.25,
    }[verdict]
