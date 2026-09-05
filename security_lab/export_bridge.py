from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from research_bundle.models import (
    CompetitionIdentity,
    EnvironmentRecord,
    KnowledgeMaterial,
    ProvenanceRecord,
    ResearchDecisionRecord,
    RobustnessResult,
    SecurityResearchBundle,
    SecurityResearchBundleV2,
)
from research_bundle.models import Finding as BundleFinding
from research_bundle.models import Hypothesis as BundleHypothesis
from research_bundle.models import Observation as BundleObservation
from research_bundle.models import Probe as BundleProbe
from research_bundle.models import Trajectory as BundleTrajectory

from .models import Hypothesis, Observation, Probe, ProbeVerdict, Trajectory
from .reproducibility import stable_hash
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


def build_research_bundle_v2(
    *,
    competition_slug: str,
    competition_name: str,
    hypotheses: list[Hypothesis],
    probes: list[Probe],
    observations: list[Observation],
    trajectories: list[Trajectory],
    robustness_by_family: dict[str, RobustnessEnvelope],
    knowledge_materials: list[KnowledgeMaterial] | None = None,
    research_decisions: list[ResearchDecisionRecord] | None = None,
    environments: list[EnvironmentRecord] | None = None,
    generated_at: datetime | None = None,
) -> SecurityResearchBundleV2:
    """Build the lossless v2 research artifact without minting BLACK knowledge types."""

    base = build_research_bundle(
        competition_slug=competition_slug,
        competition_name=competition_name,
        hypotheses=hypotheses,
        probes=probes,
        observations=observations,
        trajectories=trajectories,
        robustness_by_family=robustness_by_family,
        generated_at=generated_at,
    )
    payload = base.model_dump()
    payload.pop("schema_version", None)

    derived_materials = list(knowledge_materials or [])
    existing_material_ids = {item.material_id for item in derived_materials}
    for observation in observations:
        material_id = f"material::{observation.observation_id}"
        if material_id in existing_material_ids:
            continue
        derived_materials.append(_observation_material(observation))
        existing_material_ids.add(material_id)

    resolved_environments = list(environments or [])
    if environments is None:
        resolved_environments = _environment_records(trajectories)

    return SecurityResearchBundleV2(
        **payload,
        knowledge_materials=derived_materials,
        research_decisions=list(research_decisions or []),
        environments=resolved_environments,
    )


def _observation_material(observation: Observation) -> KnowledgeMaterial:
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
        statement=(
            f"research observation {observation.observation_id} produced "
            f"{observation.verdict.value.lower()}"
        ),
        evidence_refs=list(observation.evidence_refs),
        metrics=dict(observation.metrics),
        tags=["security_lab", observation.verdict.value.lower()],
        confidence=confidence,
    )


def _environment_records(trajectories: list[Trajectory]) -> list[EnvironmentRecord]:
    records: dict[str, EnvironmentRecord] = {}
    for trajectory in trajectories:
        environment = trajectory.environment
        environment_id = f"environment::{stable_hash(asdict(environment))[:20]}"
        records[environment_id] = EnvironmentRecord(
            environment_id=environment_id,
            model_id=environment.model_id,
            runtime_id=environment.runtime_id,
            compiler_id=environment.compiler_id,
            quantization=environment.quantization,
            runtime_version=environment.runtime_version,
            tokenizer_revision=environment.tokenizer_revision,
            tool_surface_hash=environment.tool_surface_hash,
            evaluator_hash=environment.evaluator_hash,
        )
    return [records[key] for key in sorted(records)]


def _family_for_probe(probe_id: str, hypotheses: list[Hypothesis]) -> str:
    hypothesis_id = probe_id.split("::", 1)[0]
    for hypothesis in hypotheses:
        if hypothesis.hypothesis_id == hypothesis_id:
            return hypothesis.family_id
    return "unknown"
