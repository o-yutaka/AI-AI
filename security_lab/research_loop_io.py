from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from research_bundle.models import KnowledgeMaterial, SecurityResearchBundleV2

from .budget import allocate_budget
from .budget_ledger import BudgetLedger
from .export_bridge import build_research_bundle_v2
from .models import (
    EnvironmentIdentity,
    Hypothesis,
    Observation,
    Probe,
    ProbeVerdict,
    Split,
    Trajectory,
)
from .research_loop import recorded_probe_executor, run_research_loop
from .robustness import RobustnessSample, build_robustness_envelope


def run_research_loop_from_mapping(raw: dict[str, Any]) -> SecurityResearchBundleV2:
    competition = _dict(raw["competition"])
    hypotheses = [_hypothesis(_dict(item)) for item in _list(raw["hypotheses"])]
    probes = [_probe(_dict(item)) for item in _list(raw["probes"])]
    recorded = [_observation(_dict(item)) for item in _list(raw["recorded_observations"])]
    recorded_by_probe = {item.probe_id: item for item in recorded}
    if len(recorded_by_probe) != len(recorded):
        raise ValueError("recorded observations require unique probe ids")

    budget = BudgetLedger(allocate_budget(float(raw["total_budget_units"])))
    max_steps_raw = raw.get("max_steps")
    max_steps = int(max_steps_raw) if max_steps_raw is not None else None
    result = run_research_loop(
        hypotheses=hypotheses,
        probes=probes,
        executor=recorded_probe_executor(recorded_by_probe),
        budget=budget,
        max_steps=max_steps,
    )

    trajectories = [_trajectory(_dict(item)) for item in _list(raw.get("trajectories", []))]
    robustness_by_family = {
        family_id: build_robustness_envelope(
            [_robustness_sample(_dict(item)) for item in _list(samples)]
        )
        for family_id, samples in sorted(_dict(raw.get("robustness", {})).items())
    }
    belief_materials = [
        KnowledgeMaterial(
            material_id=f"belief::{hypothesis_id}",
            kind="HYPOTHESIS_UPDATE",
            subject_ref=hypothesis_id,
            statement="research-loop posterior updated from recorded falsification evidence",
            evidence_refs=[],
            metrics={
                "prior": state.prior,
                "posterior": state.posterior,
                "support_count": float(state.support_count),
                "refutation_count": float(state.refutation_count),
                "inconclusive_count": float(state.inconclusive_count),
                "blocked_count": float(state.blocked_count),
            },
            tags=["belief", "research_loop"],
            confidence=_posterior_confidence(state.posterior),
        )
        for hypothesis_id, state in sorted(result.evidence_states.items())
    ]

    generated_at = _timestamp(raw.get("generated_at"))
    return build_research_bundle_v2(
        competition_slug=str(competition["competition_slug"]),
        competition_name=str(competition["competition_name"]),
        hypotheses=hypotheses,
        probes=probes,
        observations=list(result.observations),
        trajectories=trajectories,
        robustness_by_family=robustness_by_family,
        knowledge_materials=belief_materials,
        research_decisions=list(result.decisions),
        generated_at=generated_at,
    )


def _hypothesis(raw: dict[str, Any]) -> Hypothesis:
    return Hypothesis(
        hypothesis_id=str(raw["hypothesis_id"]),
        family_id=str(raw["family_id"]),
        statement=str(raw["statement"]),
        falsification_condition=str(raw["falsification_condition"]),
        expected_observable=str(raw["expected_observable"]),
        prior=float(raw.get("prior", 0.5)),
    )


def _probe(raw: dict[str, Any]) -> Probe:
    return Probe(
        probe_id=str(raw["probe_id"]),
        hypothesis_id=str(raw["hypothesis_id"]),
        split=Split(str(raw["split"])),
        input_payload=_dict(raw.get("input_payload", {})),
        expected_observable=str(raw["expected_observable"]),
        budget_cost=float(raw.get("budget_cost", 1.0)),
    )


def _observation(raw: dict[str, Any]) -> Observation:
    return Observation(
        observation_id=str(raw["observation_id"]),
        probe_id=str(raw["probe_id"]),
        observable=str(raw["observable"]),
        verdict=ProbeVerdict(str(raw["verdict"])),
        metrics={key: float(value) for key, value in _dict(raw.get("metrics", {})).items()},
        evidence_refs=tuple(str(item) for item in _list(raw.get("evidence_refs", []))),
    )


def _trajectory(raw: dict[str, Any]) -> Trajectory:
    environment = _dict(raw["environment"])
    return Trajectory(
        trajectory_id=str(raw["trajectory_id"]),
        probe_id=str(raw["probe_id"]),
        environment=EnvironmentIdentity(
            model_id=str(environment["model_id"]),
            runtime_id=str(environment["runtime_id"]),
            quantization=_optional_str(environment.get("quantization")),
            tool_surface_hash=_optional_str(environment.get("tool_surface_hash")),
            evaluator_hash=_optional_str(environment.get("evaluator_hash")),
            model_revision=_optional_str(environment.get("model_revision")),
            runtime_version=_optional_str(environment.get("runtime_version")),
            tokenizer_revision=_optional_str(environment.get("tokenizer_revision")),
            compiler_id=_optional_str(environment.get("compiler_id")),
        ),
        steps=tuple(_dict(item) for item in _list(raw.get("steps", []))),
        token_count=int(raw.get("token_count", 0)),
        latency_ms=float(raw.get("latency_ms", 0.0)),
        completed=bool(raw.get("completed", True)),
    )


def _robustness_sample(raw: dict[str, Any]) -> RobustnessSample:
    margin = raw.get("margin")
    return RobustnessSample(
        condition_id=str(raw["condition_id"]),
        score=float(raw["score"]),
        success=bool(raw["success"]),
        margin=float(margin) if margin is not None else None,
    )


def _timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if not isinstance(value, str):
        raise ValueError("generated_at must be an ISO timestamp string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("generated_at must include timezone information")
    return parsed


def _posterior_confidence(posterior: float) -> float:
    return min(1.0, max(0.0, abs(posterior - 0.5) * 2.0))


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("expected JSON array")
    return value


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
