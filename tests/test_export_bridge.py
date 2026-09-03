from datetime import UTC, datetime

from research_bundle.canonical import bundle_sha256
from security_lab import (
    EnvironmentIdentity,
    Hypothesis,
    Observation,
    ProbeVerdict,
    RobustnessSample,
    build_robustness_envelope,
    compile_probe,
)
from security_lab.export_bridge import build_research_bundle
from security_lab.models import Trajectory


def test_engine_exports_canonical_research_bundle_without_black_authority() -> None:
    generated = datetime(2026, 9, 3, tzinfo=UTC)
    hypothesis = Hypothesis("h1", "family-a", "statement", "false when x", "signal")
    probe = compile_probe(hypothesis, {"case": "synthetic"})
    trajectory = Trajectory(
        trajectory_id=f"trajectory::{probe.probe_id}",
        probe_id=probe.probe_id,
        environment=EnvironmentIdentity("model", "runtime"),
        steps=({"step": "observe"},),
    )
    observation = Observation(
        observation_id=f"observation::{probe.probe_id}",
        probe_id=probe.probe_id,
        observable="signal",
        verdict=ProbeVerdict.SUPPORTED,
        evidence_refs=(trajectory.trajectory_id,),
    )
    envelope = build_robustness_envelope(
        [RobustnessSample("c1", 1.0, True, 0.5)]
    )

    first = build_research_bundle(
        competition_slug="ai-agent-security-multi-step-tool-attacks",
        competition_name="AI Agent Security - Multi-Step Tool Attacks",
        hypotheses=[hypothesis],
        probes=[probe],
        observations=[observation],
        trajectories=[trajectory],
        robustness_by_family={"family-a": envelope},
        generated_at=generated,
    )
    second = build_research_bundle(
        competition_slug="ai-agent-security-multi-step-tool-attacks",
        competition_name="AI Agent Security - Multi-Step Tool Attacks",
        hypotheses=[hypothesis],
        probes=[probe],
        observations=[observation],
        trajectories=[trajectory],
        robustness_by_family={"family-a": envelope},
        generated_at=generated,
    )
    assert bundle_sha256(first) == bundle_sha256(second)
    payload = first.model_dump(mode="json")
    forbidden = {
        "experience",
        "lesson",
        "adoption_authorized",
        "execution_authorized",
        "promotion_authorized",
    }
    assert forbidden.isdisjoint(payload)
