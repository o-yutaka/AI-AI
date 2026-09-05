from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from research_bundle.models import KnowledgeMaterial

from .evaluator import EvaluatorSpec, decompose_evaluator
from .models import ProbeVerdict
from .reproducibility import stable_hash


@dataclass(frozen=True)
class EvaluatorClaimState:
    claim_id: str
    dimension: str
    statement: str
    probability: float = 0.5
    support_count: int = 0
    refutation_count: int = 0
    inconclusive_count: int = 0
    blocked_count: int = 0
    last_signal_id: str | None = None


@dataclass(frozen=True)
class EvaluatorProbeCandidate:
    probe_id: str
    claim_ids: tuple[str, ...]
    cost_units: float
    discriminatory_power: float = 1.0


@dataclass(frozen=True)
class EvaluatorSignal:
    signal_id: str
    probe_id: str
    verdict: ProbeVerdict
    evidence_refs: tuple[str, ...] = ()
    metrics: Mapping[str, float] | None = None


@dataclass(frozen=True)
class EvaluatorProbeSelection:
    probe_id: str
    information_gain_proxy: float
    claim_ids: tuple[str, ...]
    cost_units: float


def initialize_evaluator_claims(spec: EvaluatorSpec) -> dict[str, EvaluatorClaimState]:
    """Convert evaluator dimensions into stable, neutral research claims."""

    claims: dict[str, EvaluatorClaimState] = {}
    for dimension in decompose_evaluator(spec):
        for statement in dimension.claims:
            claim_id = "evaluator-claim::" + stable_hash(
                {
                    "evaluator_id": spec.evaluator_id,
                    "dimension": dimension.dimension,
                    "statement": statement,
                }
            )[:24]
            claims[claim_id] = EvaluatorClaimState(
                claim_id=claim_id,
                dimension=dimension.dimension,
                statement=statement,
            )
    return claims


def select_evaluator_probe(
    probes: Sequence[EvaluatorProbeCandidate],
    claims: Mapping[str, EvaluatorClaimState],
    completed_probe_ids: set[str] | frozenset[str] = frozenset(),
) -> EvaluatorProbeSelection | None:
    """Choose the probe with the largest uncertainty-reduction proxy per cost.

    This is deliberately named a proxy: without a calibrated outcome model, the
    system must not claim mathematically exact expected information gain.
    """

    best: EvaluatorProbeSelection | None = None
    for probe in probes:
        if probe.probe_id in completed_probe_ids:
            continue
        if probe.cost_units <= 0:
            raise ValueError("evaluator probe cost_units must be positive")
        if not 0.0 <= probe.discriminatory_power <= 1.0:
            raise ValueError("discriminatory_power must be between 0 and 1")
        if not probe.claim_ids:
            raise ValueError("evaluator probe must target at least one claim")

        entropy = 0.0
        for claim_id in probe.claim_ids:
            claim = claims.get(claim_id)
            if claim is None:
                raise ValueError(f"evaluator probe references unknown claim: {claim_id}")
            entropy += _binary_entropy(claim.probability)
        score = entropy * probe.discriminatory_power / probe.cost_units
        candidate = EvaluatorProbeSelection(
            probe_id=probe.probe_id,
            information_gain_proxy=score,
            claim_ids=tuple(sorted(probe.claim_ids)),
            cost_units=probe.cost_units,
        )
        if best is None or _selection_key(candidate) < _selection_key(best):
            best = candidate
    return best


def update_evaluator_claims(
    claims: Mapping[str, EvaluatorClaimState],
    probe: EvaluatorProbeCandidate,
    signal: EvaluatorSignal,
) -> dict[str, EvaluatorClaimState]:
    if signal.probe_id != probe.probe_id:
        raise ValueError("evaluator signal is bound to a different probe")

    updated = dict(claims)
    for claim_id in probe.claim_ids:
        claim = claims.get(claim_id)
        if claim is None:
            raise ValueError(f"evaluator probe references unknown claim: {claim_id}")
        probability = _updated_probability(claim.probability, signal.verdict)
        counters = {
            "support_count": claim.support_count,
            "refutation_count": claim.refutation_count,
            "inconclusive_count": claim.inconclusive_count,
            "blocked_count": claim.blocked_count,
        }
        counter = {
            ProbeVerdict.SUPPORTED: "support_count",
            ProbeVerdict.REFUTED: "refutation_count",
            ProbeVerdict.INCONCLUSIVE: "inconclusive_count",
            ProbeVerdict.BLOCKED: "blocked_count",
        }[signal.verdict]
        counters[counter] += 1
        updated[claim_id] = replace(
            claim,
            probability=probability,
            last_signal_id=signal.signal_id,
            **counters,
        )
    return updated


def evaluator_knowledge_materials(
    claims: Mapping[str, EvaluatorClaimState],
    signals: Sequence[EvaluatorSignal],
) -> tuple[KnowledgeMaterial, ...]:
    evidence_by_signal = {signal.signal_id: signal.evidence_refs for signal in signals}
    materials = []
    for claim_id in sorted(claims):
        claim = claims[claim_id]
        refs = evidence_by_signal.get(claim.last_signal_id or "", ())
        materials.append(
            KnowledgeMaterial(
                material_id=f"evaluator-material::{claim_id}",
                kind="EVALUATOR_SIGNAL",
                subject_ref=claim_id,
                statement=(
                    f"evaluator {claim.dimension} claim remains a research hypothesis: "
                    f"{claim.statement}"
                ),
                evidence_refs=list(refs),
                metrics={
                    "probability": claim.probability,
                    "support_count": float(claim.support_count),
                    "refutation_count": float(claim.refutation_count),
                    "inconclusive_count": float(claim.inconclusive_count),
                    "blocked_count": float(claim.blocked_count),
                },
                tags=["evaluator", claim.dimension],
                confidence=abs(claim.probability - 0.5) * 2.0,
            )
        )
    return tuple(materials)


def _binary_entropy(probability: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("claim probability must be between 0 and 1")
    if probability in {0.0, 1.0}:
        return 0.0
    return -(
        probability * math.log2(probability)
        + (1.0 - probability) * math.log2(1.0 - probability)
    )


def _updated_probability(prior: float, verdict: ProbeVerdict) -> float:
    if verdict is ProbeVerdict.INCONCLUSIVE:
        return prior
    likelihood_ratio = {
        ProbeVerdict.SUPPORTED: 3.0,
        ProbeVerdict.REFUTED: 1.0 / 3.0,
        ProbeVerdict.BLOCKED: 0.8,
    }[verdict]
    odds = prior / max(1.0 - prior, 1e-12)
    posterior_odds = odds * likelihood_ratio
    return posterior_odds / (1.0 + posterior_odds)


def _selection_key(selection: EvaluatorProbeSelection) -> tuple[float, float, str]:
    return (
        -selection.information_gain_proxy,
        selection.cost_units,
        selection.probe_id,
    )
