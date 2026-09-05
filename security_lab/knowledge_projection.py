from __future__ import annotations

from collections.abc import Sequence

from research_bundle.models import KnowledgeMaterial

from .failure_correlation import FailureCorrelationGraph
from .minimum_trace import MinimumWinningTrace
from .nuisance import NuisanceSensitivityReport
from .runtime_sensitivity import RuntimeSensitivityReport
from .semantic_genome import SemanticGenome
from .throughput import ThroughputEstimate
from .transfer import RidgeTransferEstimate, TransferEstimate


def runtime_sensitivity_material(
    report: RuntimeSensitivityReport,
    *,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    return KnowledgeMaterial(
        material_id=f"runtime-sensitivity::{report.candidate_id}",
        kind="RUNTIME_SENSITIVITY",
        subject_ref=report.candidate_id,
        statement="candidate runtime sensitivity was measured across explicit runtime variants",
        evidence_refs=list(evidence_refs),
        metrics={
            "runtime_count": float(report.runtime_count),
            "success_rate": report.success_rate,
            "mean_score": report.mean_score,
            "worst_score": report.worst_score,
            "best_score": report.best_score,
            "score_range": report.score_range,
            "failed_runtime_count": float(len(report.failed_runtime_keys)),
            "fragile": float(report.fragile),
        },
        tags=["runtime_sensitivity", "fragile" if report.fragile else "stable"],
        confidence=_measurement_confidence(report.runtime_count),
    )


def transfer_behavior_material(
    subject_ref: str,
    estimate: TransferEstimate | RidgeTransferEstimate,
    *,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    metrics = {
        "slope": estimate.slope,
        "intercept": estimate.intercept,
        "residual_mae": estimate.residual_mae,
        "sample_count": float(estimate.sample_count),
    }
    tags = ["transfer", "proxy_to_target"]
    if isinstance(estimate, RidgeTransferEstimate):
        metrics["alpha"] = estimate.alpha
        metrics["residual_max"] = estimate.residual_max
        tags.append("ridge")
    else:
        tags.append("linear")
    return KnowledgeMaterial(
        material_id=f"transfer::{subject_ref}",
        kind="TRANSFER_BEHAVIOR",
        subject_ref=subject_ref,
        statement="proxy-to-target transfer behavior was calibrated from paired measurements",
        evidence_refs=list(evidence_refs),
        metrics=metrics,
        tags=tags,
        confidence=_residual_adjusted_confidence(
            estimate.sample_count,
            estimate.residual_mae,
        ),
    )


def nuisance_effect_material(
    report: NuisanceSensitivityReport,
    *,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    return KnowledgeMaterial(
        material_id=f"nuisance::{report.candidate_id}",
        kind="NUISANCE_EFFECT",
        subject_ref=report.candidate_id,
        statement="candidate stability was measured across nuisance conditions",
        evidence_refs=list(evidence_refs),
        metrics={
            "case_count": float(report.case_count),
            "success_rate": report.success_rate,
            "mean_score": report.mean_score,
            "worst_score": report.worst_score,
            "best_score": report.best_score,
            "score_range": report.score_range,
            "failed_case_count": float(len(report.failed_case_ids)),
            "fragile": float(report.fragile),
        },
        tags=["nuisance", "fragile" if report.fragile else "stable"],
        confidence=_measurement_confidence(report.case_count),
    )


def trace_reduction_material(
    result: MinimumWinningTrace,
    *,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    score = result.minimum_evaluation.score
    metrics = {
        "original_step_count": float(result.original_step_count),
        "winning_step_count": float(result.winning_step_count),
        "removed_step_count": float(result.removed_step_count),
        "replay_count": float(result.replay_count),
        "output_valid": float(result.minimum_evaluation.output_valid),
    }
    if score is not None:
        metrics["minimum_score"] = score
    return KnowledgeMaterial(
        material_id=f"trace-reduction::{result.source_trajectory_id}",
        kind="TRACE_REDUCTION",
        subject_ref=result.source_trajectory_id,
        statement="a shortest observed winning prefix was found without assuming monotonic success",
        evidence_refs=list(evidence_refs),
        metrics=metrics,
        tags=["minimum_trace", "research_replay"],
        confidence=_measurement_confidence(result.replay_count),
    )


def throughput_material(
    subject_ref: str,
    estimate: ThroughputEstimate,
    *,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    return KnowledgeMaterial(
        material_id=f"throughput::{subject_ref}",
        kind="THROUGHPUT_SIGNAL",
        subject_ref=subject_ref,
        statement="candidate throughput was estimated under an explicit time budget",
        evidence_refs=list(evidence_refs),
        metrics={
            "candidate_seconds": estimate.candidate_seconds,
            "budget_seconds": estimate.budget_seconds,
            "candidates_completed": float(estimate.candidates_completed),
            "expected_successes": estimate.expected_successes,
        },
        tags=["throughput", "budget"],
        confidence=0.5,
    )


def semantic_genome_material(
    subject_ref: str,
    genome: SemanticGenome,
    *,
    parent_ref: str | None = None,
    evidence_refs: Sequence[str] = (),
) -> KnowledgeMaterial:
    tags = ["semantic_genome", f"fingerprint:{genome.fingerprint()}"]
    if parent_ref is not None:
        tags.append(f"parent:{parent_ref}")
    return KnowledgeMaterial(
        material_id=f"semantic-genome::{genome.fingerprint()}",
        kind="SEMANTIC_GENOME",
        subject_ref=subject_ref,
        statement="semantic genome identity and structural composition were recorded",
        evidence_refs=list(evidence_refs),
        metrics={
            "gene_count": float(len(genome.genes)),
            "enabled_gene_count": float(sum(gene.enabled for gene in genome.genes)),
        },
        tags=tags,
        confidence=1.0,
    )


def failure_correlation_materials(
    graph: FailureCorrelationGraph,
    *,
    evidence_refs: Sequence[str] = (),
) -> tuple[KnowledgeMaterial, ...]:
    materials = []
    for (left, right), correlation in sorted(graph.pairwise_jaccard.items()):
        pair_ref = f"{left}::{right}"
        materials.append(
            KnowledgeMaterial(
                material_id=f"failure-correlation::{pair_ref}",
                kind="FAILURE_CORRELATION",
                subject_ref=pair_ref,
                statement="pairwise shared-failure overlap was measured across ordered contexts",
                evidence_refs=list(evidence_refs),
                metrics={
                    "jaccard": correlation,
                    "context_count": float(graph.context_count),
                },
                tags=["failure_correlation", "jaccard"],
                confidence=_measurement_confidence(graph.context_count),
            )
        )
    return tuple(materials)


def _measurement_confidence(sample_count: int) -> float:
    """Evidence-density heuristic, not held-out or BLACK verification confidence."""

    if sample_count < 0:
        raise ValueError("sample_count must be non-negative")
    return sample_count / (sample_count + 2.0) if sample_count else 0.0


def _residual_adjusted_confidence(sample_count: int, residual_mae: float) -> float:
    if residual_mae < 0:
        raise ValueError("residual_mae must be non-negative")
    return _measurement_confidence(sample_count) / (1.0 + residual_mae)
