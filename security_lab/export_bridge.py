from __future__ import annotations

from datetime import UTC, datetime

from research_bundle.models import CompetitionIdentity, ProvenanceRecord
from research_bundle.models import Finding as BundleFinding
from research_bundle.models import Hypothesis as BundleHypothesis
from research_bundle.models import Observation as BundleObservation
from research_bundle.models import Probe as BundleProbe
from research_bundle.models import RobustnessResult, SecurityResearchBundle
from research_bundle.models import Trajectory as BundleTrajectory

from .models import Hypothesis, Observation, Probe, ProbeVerdict, Trajectory
from .robustness import RobustnessEnvelope


def build_research_bundle(
    *,
    competition_slug: str,
    competition_name: str,
    hypotheses: list[Hypothesis],
    probes: list[Probe],
    observations: list[Observation],
    trajectories: list[Trajectory],
    robustness_by_family: dict[str, RobustnessEnvelope],
    generated_at: datetime | None = None,
) -> SecurityResearchBundle:
    generated = generated_at or datetime.now(UTC)
    findings: list[BundleFinding] = []
    for observation in observations:
        if observation.verdict not in {ProbeVerdict.SUPPORTED, ProbeVerdict.REFUTED}:
            continue
        family = _family_for_probe(observation.probe_id, hypotheses)
        findings.append(
            BundleFinding(
                finding_id=f"finding::{observation.observation_id}",
                family=family,
                statement=(
                    f"probe {observation.probe_id} was "
                    f"{observation.verdict.value.lower()}"
                ),
                evidence_refs=list(observation.evidence_refs),
                scope="research_observation",
                confidence=1.0 if observation.verdict is ProbeVerdict.SUPPORTED else 0.75,
            )
        )

    robustness = [
        RobustnessResult(
            result_id=f"robustness::{family_id}",
            candidate_id=family_id,
            evaluation_scope="family",
            trials=envelope.sample_count,
            successes=round(envelope.success_rate * envelope.sample_count),
            failures=(
                envelope.sample_count
                - round(envelope.success_rate * envelope.sample_count)
            ),
            metric_name="worst_score",
            metric_value=envelope.worst_score,
        )
        for family_id, envelope in sorted(robustness_by_family.items())
    ]

    return SecurityResearchBundle(
        competition=CompetitionIdentity(
            competition_slug=competition_slug,
            competition_name=competition_name,
        ),
        generated_at=generated,
        hypotheses=[
            BundleHypothesis(
                hypothesis_id=item.hypothesis_id,
                family=item.family_id,
                statement=item.statement,
                falsification_condition=item.falsification_condition,
            )
            for item in hypotheses
        ],
        probes=[
            BundleProbe(
                probe_id=item.probe_id,
                hypothesis_id=item.hypothesis_id,
                probe_kind="falsification",
                objective="observe evaluator behavior without minting authority",
                expected_observable=item.expected_observable,
                budget_units=item.budget_cost,
            )
            for item in probes
        ],
        observations=[
            BundleObservation(
                observation_id=item.observation_id,
                probe_id=item.probe_id,
                observed_at=generated,
                observable=item.observable,
                value={"verdict": item.verdict.value, "metrics": item.metrics},
                source="security_lab.replay",
            )
            for item in observations
        ],
        trajectories=[
            BundleTrajectory(
                trajectory_id=item.trajectory_id,
                run_id=item.probe_id,
                ordered_event_refs=[
                    f"step:{index}" for index, _ in enumerate(item.steps)
                ],
                outcome="UNKNOWN",
                completion=item.completed,
            )
            for item in trajectories
        ],
        findings=findings,
        robustness_results=robustness,
        provenance=[
            ProvenanceRecord(
                provenance_id="provenance::security-lab",
                source_kind="internal_research_runtime",
                source_ref="security_lab",
                captured_at=generated,
            )
        ],
    )


def _family_for_probe(probe_id: str, hypotheses: list[Hypothesis]) -> str:
    hypothesis_id = probe_id.split("::", 1)[0]
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id == hypothesis_id:
            return hypothesis.family_id
    return "unknown"
