from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_bundle import bundle_sha256
from security_lab.budget import allocate_budget
from security_lab.budget_ledger import BudgetLedger
from security_lab.hypothesis import (
    HypothesisGraph,
    HypothesisRelation,
    HypothesisRelationType,
    summarize_hypothesis_evidence,
)
from security_lab.models import Hypothesis, Observation, Probe, ProbeVerdict, Split
from security_lab.research_loop import recorded_probe_executor, run_research_loop
from security_lab.research_loop_io import run_research_loop_from_mapping


def _hypothesis(hypothesis_id: str, prior: float = 0.5) -> Hypothesis:
    return Hypothesis(
        hypothesis_id=hypothesis_id,
        family_id="family-a",
        statement=f"statement {hypothesis_id}",
        falsification_condition=f"falsify {hypothesis_id}",
        expected_observable="signal",
        prior=prior,
    )


def _probe(hypothesis_id: str, cost: float, split: Split = Split.DEV) -> Probe:
    return Probe(
        probe_id=f"{hypothesis_id}::p1",
        hypothesis_id=hypothesis_id,
        split=split,
        input_payload={"synthetic": True},
        expected_observable="signal",
        budget_cost=cost,
    )


def _observation(hypothesis_id: str, verdict: ProbeVerdict) -> Observation:
    return Observation(
        observation_id=f"observation::{hypothesis_id}",
        probe_id=f"{hypothesis_id}::p1",
        observable="signal",
        verdict=verdict,
        metrics={"score": 1.0 if verdict is ProbeVerdict.SUPPORTED else 0.0},
        evidence_refs=(f"evidence::{hypothesis_id}",),
    )


def test_hypothesis_graph_preserves_typed_relations_and_posterior_evidence() -> None:
    hypotheses = [_hypothesis("h1"), _hypothesis("h2")]
    graph = HypothesisGraph(
        hypotheses,
        [
            HypothesisRelation(
                "h1",
                "h2",
                HypothesisRelationType.CONTRADICTS,
                ("evidence::relation",),
            )
        ],
    )

    relation = graph.relations_from("h1")[0]
    assert relation.target_id == "h2"
    assert relation.relation is HypothesisRelationType.CONTRADICTS

    states = summarize_hypothesis_evidence(
        graph,
        [
            _observation("h1", ProbeVerdict.SUPPORTED),
            _observation("h2", ProbeVerdict.REFUTED),
        ],
    )
    assert states["h1"].posterior > states["h1"].prior
    assert states["h1"].support_count == 1
    assert states["h2"].posterior < states["h2"].prior
    assert states["h2"].refutation_count == 1


def test_research_loop_selects_uncertainty_per_cost_and_records_rejections() -> None:
    hypotheses = [_hypothesis("h1"), _hypothesis("h2")]
    probes = [_probe("h1", 0.5), _probe("h2", 1.0)]
    observations = {
        "h1::p1": _observation("h1", ProbeVerdict.SUPPORTED),
        "h2::p1": _observation("h2", ProbeVerdict.REFUTED),
    }
    result = run_research_loop(
        hypotheses=hypotheses,
        probes=probes,
        executor=recorded_probe_executor(observations),
        budget=BudgetLedger(allocate_budget(8.0)),
        max_steps=1,
    )

    assert result.completed_probe_ids == ("h1::p1",)
    assert result.decisions[0].selected == ["h1::p1"]
    assert result.decisions[0].rejected == ["h2::p1"]
    assert result.decisions[0].authority == "NONE"
    assert result.stopped_reason == "MAX_STEPS_REACHED"


def test_research_loop_fails_closed_on_held_out_optimization_leakage() -> None:
    hypothesis = _hypothesis("h1")
    probe = _probe("h1", 0.5, Split.HELD_OUT)
    with pytest.raises(ValueError, match="split leakage guard"):
        run_research_loop(
            hypotheses=[hypothesis],
            probes=[probe],
            executor=recorded_probe_executor(
                {probe.probe_id: _observation("h1", ProbeVerdict.SUPPORTED)}
            ),
            budget=BudgetLedger(allocate_budget(8.0)),
            max_steps=1,
        )


def test_example_research_run_produces_deterministic_lossless_v2_bundle() -> None:
    raw = json.loads(Path("examples/research-loop.example.json").read_text(encoding="utf-8"))
    first = run_research_loop_from_mapping(raw)
    second = run_research_loop_from_mapping(raw)

    assert first.schema_version == "security-research-bundle.v2"
    assert bundle_sha256(first) == bundle_sha256(second)
    assert len(first.research_decisions) == 2
    assert {item.subject_ref for item in first.knowledge_materials} >= {"h1", "h2"}
    assert len(first.environments) == 1
    assert first.environments[0].model_revision == "rev-a"
    assert all(item.authority == "NONE" for item in first.research_decisions)
    assert all(item.independently_verified is False for item in first.knowledge_materials)
