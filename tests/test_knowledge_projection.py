from __future__ import annotations

from security_lab.failure_correlation import FailureCorrelationGraph
from security_lab.knowledge_projection import (
    failure_correlation_materials,
    nuisance_effect_material,
    runtime_sensitivity_material,
    semantic_genome_material,
    throughput_material,
    trace_reduction_material,
    transfer_behavior_material,
)
from security_lab.minimum_trace import MinimumWinningTrace, TraceEvaluation
from security_lab.nuisance import NuisanceSensitivityReport
from security_lab.runtime_sensitivity import RuntimeSensitivityReport
from security_lab.semantic_genome import GeneSlot, SemanticGene, SemanticGenome
from security_lab.throughput import ThroughputEstimate
from security_lab.transfer import RidgeTransferEstimate


def test_runtime_and_nuisance_reports_become_non_verified_material() -> None:
    runtime = runtime_sensitivity_material(
        RuntimeSensitivityReport(
            candidate_id="candidate-a",
            runtime_count=3,
            success_rate=2 / 3,
            mean_score=0.6,
            worst_score=0.2,
            best_score=0.9,
            score_range=0.7,
            failed_runtime_keys=("model|runtime|compiler|q4",),
            fragile=True,
        ),
        evidence_refs=("evidence::runtime",),
    )
    nuisance = nuisance_effect_material(
        NuisanceSensitivityReport(
            candidate_id="candidate-a",
            case_count=4,
            success_rate=0.75,
            mean_score=0.7,
            worst_score=0.3,
            best_score=0.95,
            score_range=0.65,
            failed_case_ids=("case-2",),
            fragile=True,
        )
    )

    assert runtime.kind == "RUNTIME_SENSITIVITY"
    assert runtime.metrics["fragile"] == 1.0
    assert runtime.evidence_refs == ["evidence::runtime"]
    assert runtime.independently_verified is False
    assert nuisance.kind == "NUISANCE_EFFECT"
    assert nuisance.metrics["failed_case_count"] == 1.0
    assert nuisance.independently_verified is False


def test_transfer_trace_and_throughput_are_preserved_as_measurements() -> None:
    transfer = transfer_behavior_material(
        "bf16-to-target",
        RidgeTransferEstimate(
            slope=0.8,
            intercept=0.1,
            alpha=0.5,
            residual_mae=0.05,
            residual_max=0.1,
            sample_count=5,
        ),
    )
    trace = trace_reduction_material(
        MinimumWinningTrace(
            source_trajectory_id="trajectory-a",
            original_step_count=3,
            winning_step_count=1,
            removed_step_count=2,
            replay_count=3,
            minimum_steps=({"step": 1},),
            baseline=TraceEvaluation(True, True, 0.9),
            minimum_evaluation=TraceEvaluation(True, True, 0.8),
        )
    )
    throughput = throughput_material(
        "candidate-a",
        ThroughputEstimate(
            candidate_seconds=2.0,
            budget_seconds=10.0,
            candidates_completed=5,
            expected_successes=3.5,
        ),
    )

    assert transfer.kind == "TRANSFER_BEHAVIOR"
    assert transfer.metrics["residual_max"] == 0.1
    assert trace.kind == "TRACE_REDUCTION"
    assert trace.metrics["removed_step_count"] == 2.0
    assert throughput.kind == "THROUGHPUT_SIGNAL"
    assert throughput.metrics["candidates_completed"] == 5.0
    assert all(
        item.independently_verified is False
        for item in (transfer, trace, throughput)
    )


def test_semantic_genome_projection_records_identity_not_success_claim() -> None:
    genome = SemanticGenome(
        (
            SemanticGene("g1", GeneSlot.INSTRUCTION, "neutral instruction"),
            SemanticGene("g2", GeneSlot.LAYOUT, "neutral layout", enabled=False),
        )
    )
    material = semantic_genome_material("candidate-a", genome, parent_ref="parent-a")

    assert material.kind == "SEMANTIC_GENOME"
    assert material.metrics == {"gene_count": 2.0, "enabled_gene_count": 1.0}
    assert f"fingerprint:{genome.fingerprint()}" in material.tags
    assert "parent:parent-a" in material.tags
    assert "success" not in material.statement.lower()


def test_failure_correlation_projection_is_pairwise_and_deterministic() -> None:
    graph = FailureCorrelationGraph(
        candidate_ids=("a", "b", "c"),
        context_count=4,
        pairwise_jaccard={
            ("b", "c"): 0.25,
            ("a", "c"): 0.5,
            ("a", "b"): 1.0,
        },
    )

    materials = failure_correlation_materials(graph)

    assert [item.subject_ref for item in materials] == ["a::b", "a::c", "b::c"]
    assert [item.metrics["jaccard"] for item in materials] == [1.0, 0.5, 0.25]
    assert all(item.kind == "FAILURE_CORRELATION" for item in materials)
    assert all(item.independently_verified is False for item in materials)
