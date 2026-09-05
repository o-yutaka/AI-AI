from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from security_lab.export_bridge import build_research_bundle_v2
from security_lab.models import (
    EnvironmentIdentity,
    Hypothesis,
    Observation,
    Probe,
    ProbeVerdict,
    Split,
    Trajectory,
)
from security_lab.nuisance import (
    NuisanceOutcome,
    analyze_nuisance_sensitivity,
    select_nuisance_stable_candidates,
)
from security_lab.optimizer import (
    DeterministicNeighborhoodOptimizer,
    OptimizationCandidate,
    OptimizationObservation,
    OptimizationRequest,
    select_frontier,
)
from security_lab.research_roles import (
    ResearchArtifact,
    ResearchContext,
    ResearchRole,
    orchestrate_research_roles,
)
from security_lab.robustness import RobustnessSample, build_robustness_envelope


def test_optimizer_spi_is_deterministic_and_proposal_only() -> None:
    seed = OptimizationCandidate("seed", {"value": 0})

    def neighborhood(parent: OptimizationCandidate):
        yield OptimizationCandidate("candidate-z", {"value": 2}, parent.candidate_id)
        yield OptimizationCandidate("candidate-a", {"value": 1}, parent.candidate_id)

    optimizer = DeterministicNeighborhoodOptimizer("deterministic.v1", neighborhood)
    proposals = optimizer.propose(OptimizationRequest((seed,), proposal_limit=2))

    assert [item.candidate_id for item in proposals] == ["candidate-a", "candidate-z"]
    assert all(item.parent_id == "seed" for item in proposals)


def test_frontier_prefers_pass_then_score() -> None:
    candidates = [
        OptimizationCandidate("a", {}),
        OptimizationCandidate("b", {}),
        OptimizationCandidate("c", {}),
    ]
    observations = [
        OptimizationObservation("a", 10.0, False),
        OptimizationObservation("b", 0.5, True),
        OptimizationObservation("c", 0.9, True),
    ]

    frontier = select_frontier(candidates, observations, limit=2)
    assert [item.candidate_id for item in frontier] == ["c", "b"]


def test_nuisance_screening_separates_fragile_candidate() -> None:
    stable = analyze_nuisance_sensitivity(
        [
            NuisanceOutcome("stable", "c1", True, 0.9),
            NuisanceOutcome("stable", "c2", True, 0.85),
        ],
        maximum_score_range=0.1,
    )
    fragile = analyze_nuisance_sensitivity(
        [
            NuisanceOutcome("fragile", "c1", True, 0.9),
            NuisanceOutcome("fragile", "c2", False, 0.1),
        ],
        minimum_success_rate=1.0,
        maximum_score_range=0.2,
    )

    assert stable.fragile is False
    assert fragile.fragile is True
    assert fragile.failed_case_ids == ("c2",)
    assert select_nuisance_stable_candidates([fragile, stable]) == ("stable",)


@dataclass(frozen=True)
class _RolePort:
    role: ResearchRole

    def run(self, context: ResearchContext):
        return (
            ResearchArtifact(
                artifact_id=f"{self.role.value.lower()}::1",
                role=self.role,
                kind="research_signal",
                subject_ref=context.subject_ref,
                statement=f"{self.role.value} observation",
                evidence_refs=context.evidence_refs,
            ),
        )


def test_research_roles_run_in_explicit_non_authoritative_order() -> None:
    result = orchestrate_research_roles(
        ResearchContext("candidate-a", {}, ("evidence::1",)),
        [_RolePort(ResearchRole.JUDGE), _RolePort(ResearchRole.RED)],
    )

    assert result.roles_completed == (ResearchRole.RED, ResearchRole.JUDGE)
    assert [item.role for item in result.artifacts] == [ResearchRole.RED, ResearchRole.JUDGE]
    assert all(item.authority == "NONE" for item in result.artifacts)


def test_research_roles_fail_closed_on_authority() -> None:
    @dataclass(frozen=True)
    class BadPort:
        role: ResearchRole = ResearchRole.JUDGE

        def run(self, context: ResearchContext):
            return (
                ResearchArtifact(
                    "bad::1",
                    self.role,
                    "verdict",
                    context.subject_ref,
                    "bad authority",
                    authority="DECISION",
                ),
            )

    with pytest.raises(ValueError, match="cannot carry authority"):
        orchestrate_research_roles(ResearchContext("x", {}), [BadPort()])


def test_v2_bundle_preserves_observation_and_environment_for_black_absorption() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="h1",
        family_id="family-a",
        statement="neutral benchmark hypothesis",
        falsification_condition="held evaluator observation refutes it",
        expected_observable="signal",
    )
    probe = Probe(
        probe_id="h1::p1",
        hypothesis_id="h1",
        split=Split.DEV,
        input_payload={},
        expected_observable="signal",
    )
    observation = Observation(
        observation_id="o1",
        probe_id=probe.probe_id,
        observable="signal",
        verdict=ProbeVerdict.SUPPORTED,
        metrics={"score": 0.8},
        evidence_refs=("evidence::o1",),
    )
    trajectory = Trajectory(
        trajectory_id="t1",
        probe_id=probe.probe_id,
        environment=EnvironmentIdentity(
            model_id="model-a",
            runtime_id="runtime-a",
            quantization="q4",
            runtime_version="1.2.3",
            tokenizer_revision="tok-1",
            compiler_id="compiler-a",
        ),
        steps=({"kind": "synthetic-step"},),
    )
    robustness = build_robustness_envelope(
        [RobustnessSample("condition-a", 0.8, True)]
    )

    bundle = build_research_bundle_v2(
        competition_slug="ai-agent-security-multi-step-tool-attacks",
        competition_name="AI Agent Security - Multi-Step Tool Attacks",
        hypotheses=[hypothesis],
        probes=[probe],
        observations=[observation],
        trajectories=[trajectory],
        robustness_by_family={"family-a": robustness},
        generated_at=datetime(2026, 9, 6, tzinfo=UTC),
    )

    assert bundle.schema_version == "security-research-bundle.v2"
    assert len(bundle.knowledge_materials) == 1
    assert bundle.knowledge_materials[0].kind == "SUCCESS_CONDITION"
    assert bundle.knowledge_materials[0].independently_verified is False
    assert len(bundle.environments) == 1
    assert bundle.environments[0].runtime_version == "1.2.3"
    payload = bundle.model_dump(mode="json")
    assert "experience" not in payload
    assert "lesson" not in payload
