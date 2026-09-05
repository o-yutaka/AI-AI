from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from research_bundle.models import (
    KnowledgeMaterial,
    ResearchDecisionRecord,
)

from .belief import (
    HypothesisBelief,
    initial_beliefs,
    select_next_probe,
    update_belief,
)
from .budget_ledger import BudgetLedger, BudgetStage
from .hypothesis import (
    HypothesisEvidenceState,
    HypothesisGraph,
    summarize_hypothesis_evidence,
)
from .leakage import ResearchPurpose, assert_split_allowed
from .models import Hypothesis, Observation, Probe, ProbeVerdict


ProbeExecutor = Callable[[Probe], Observation]


@dataclass(frozen=True)
class ResearchLoopResult:
    observations: tuple[Observation, ...]
    beliefs: Mapping[str, HypothesisBelief]
    evidence_states: Mapping[str, HypothesisEvidenceState]
    decisions: tuple[ResearchDecisionRecord, ...]
    knowledge_materials: tuple[KnowledgeMaterial, ...]
    completed_probe_ids: tuple[str, ...]
    stopped_reason: str


def run_research_loop(
    *,
    hypotheses: Sequence[Hypothesis],
    probes: Sequence[Probe],
    executor: ProbeExecutor,
    budget: BudgetLedger,
    seed_observations: Sequence[Observation] = (),
    max_steps: int | None = None,
) -> ResearchLoopResult:
    """Run bounded falsification research without touching held-out splits.

    Probe selection uses uncertainty-per-cost. Every selected and remaining path is
    preserved in a non-authoritative ResearchDecisionRecord. The executor is caller-owned,
    so this loop can operate against synthetic, replayed, or benchmark environments.
    """

    if max_steps is not None and max_steps < 0:
        raise ValueError("max_steps must be non-negative")

    graph = HypothesisGraph(list(hypotheses))
    hypothesis_ids = {item.hypothesis_id for item in hypotheses}
    probe_by_id = {item.probe_id: item for item in probes}
    if len(probe_by_id) != len(probes):
        raise ValueError("probe ids must be unique")
    for probe in probes:
        if probe.hypothesis_id not in hypothesis_ids:
            raise ValueError(
                f"probe {probe.probe_id} references unknown hypothesis {probe.hypothesis_id}"
            )

    beliefs = initial_beliefs(list(hypotheses))
    observations = list(seed_observations)
    completed: set[str] = set()
    decisions: list[ResearchDecisionRecord] = []
    materials: list[KnowledgeMaterial] = []

    for observation in seed_observations:
        if observation.probe_id in completed:
            raise ValueError(f"duplicate seed observation for probe {observation.probe_id}")
        probe = probe_by_id.get(observation.probe_id)
        if probe is None:
            raise ValueError(
                f"seed observation references unknown probe {observation.probe_id}"
            )
        assert_split_allowed(ResearchPurpose.FALSIFICATION, probe.split)
        completed.add(observation.probe_id)
        belief = beliefs[probe.hypothesis_id]
        beliefs[probe.hypothesis_id] = update_belief(belief, observation)

    steps = 0
    stopped_reason = "NO_AVAILABLE_PROBE"
    while True:
        if max_steps is not None and steps >= max_steps:
            stopped_reason = "MAX_STEPS_REACHED"
            break

        next_probe = select_next_probe(list(probes), beliefs, completed)
        if next_probe is None:
            stopped_reason = "NO_AVAILABLE_PROBE"
            break
        assert_split_allowed(ResearchPurpose.FALSIFICATION, next_probe.split)

        remaining = budget.remaining(BudgetStage.FALSIFICATION)
        if next_probe.budget_cost > remaining + 1e-12:
            stopped_reason = "FALSIFICATION_BUDGET_EXHAUSTED"
            decisions.append(
                ResearchDecisionRecord(
                    decision_id=f"research-decision::budget::{steps:05d}",
                    stage=BudgetStage.FALSIFICATION.value,
                    candidates_considered=[next_probe.probe_id],
                    selected=[],
                    rejected=[next_probe.probe_id],
                    rationale=(
                        "probe rejected because remaining falsification budget "
                        "is insufficient"
                    ),
                    evidence_refs=[],
                    budget_units_spent=0.0,
                )
            )
            break

        budget.charge(BudgetStage.FALSIFICATION, next_probe.budget_cost)
        observation = executor(next_probe)
        if observation.probe_id != next_probe.probe_id:
            raise ValueError("probe executor returned observation bound to a different probe")

        observations.append(observation)
        completed.add(next_probe.probe_id)
        belief = beliefs[next_probe.hypothesis_id]
        beliefs[next_probe.hypothesis_id] = update_belief(belief, observation)

        rejected = sorted(
            probe.probe_id
            for probe in probes
            if probe.probe_id not in completed
        )
        decisions.append(
            ResearchDecisionRecord(
                decision_id=f"research-decision::probe::{steps:05d}",
                stage=BudgetStage.FALSIFICATION.value,
                candidates_considered=[next_probe.probe_id, *rejected],
                selected=[next_probe.probe_id],
                rejected=rejected,
                rationale="selected by highest hypothesis uncertainty per budget cost",
                evidence_refs=list(observation.evidence_refs),
                budget_units_spent=next_probe.budget_cost,
            )
        )
        materials.append(_knowledge_from_observation(observation))
        steps += 1

    return ResearchLoopResult(
        observations=tuple(observations),
        beliefs=dict(beliefs),
        evidence_states=summarize_hypothesis_evidence(graph, observations),
        decisions=tuple(decisions),
        knowledge_materials=tuple(materials),
        completed_probe_ids=tuple(sorted(completed)),
        stopped_reason=stopped_reason,
    )


def recorded_probe_executor(
    observations_by_probe: Mapping[str, Observation],
) -> ProbeExecutor:
    """Build a deterministic executor over already-recorded benchmark evidence."""

    def execute(probe: Probe) -> Observation:
        try:
            return observations_by_probe[probe.probe_id]
        except KeyError as exc:
            raise ValueError(f"no recorded observation for probe {probe.probe_id}") from exc

    return execute


def _knowledge_from_observation(observation: Observation) -> KnowledgeMaterial:
    kind = {
        ProbeVerdict.SUPPORTED: "SUCCESS_CONDITION",
        ProbeVerdict.REFUTED: "HYPOTHESIS_UPDATE",
        ProbeVerdict.INCONCLUSIVE: "HYPOTHESIS_UPDATE",
        ProbeVerdict.BLOCKED: "FAILURE_MODE",
    }[observation.verdict]
    confidence = {
        ProbeVerdict.SUPPORTED: 1.0,
        ProbeVerdict.REFUTED: 0.9,
        ProbeVerdict.INCONCLUSIVE: 0.5,
        ProbeVerdict.BLOCKED: 0.75,
    }[observation.verdict]
    return KnowledgeMaterial(
        material_id=f"material::{observation.observation_id}",
        kind=kind,
        subject_ref=observation.probe_id,
        statement=f"research loop observed {observation.verdict.value.lower()}",
        evidence_refs=list(observation.evidence_refs),
        metrics=dict(observation.metrics),
        tags=["research_loop", observation.verdict.value.lower()],
        confidence=confidence,
    )
