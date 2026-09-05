from __future__ import annotations

from security_lab.evaluator import EvaluatorSpec
from security_lab.evaluator_intelligence import (
    EvaluatorProbeCandidate,
    EvaluatorSignal,
    evaluator_knowledge_materials,
    initialize_evaluator_claims,
    select_evaluator_probe,
    update_evaluator_claims,
)
from security_lab.models import ProbeVerdict


def _spec() -> EvaluatorSpec:
    return EvaluatorSpec(
        evaluator_id="evaluator-a",
        score_predicates=("score>=threshold",),
        replay_semantics=("same-runtime",),
        guardrail_classes=("policy-a",),
        parser_constraints=("tool-json",),
        time_budget_seconds=60,
        candidate_budget=10,
    )


def test_claim_identity_is_stable_and_dimension_complete() -> None:
    first = initialize_evaluator_claims(_spec())
    second = initialize_evaluator_claims(_spec())

    assert first == second
    assert {item.dimension for item in first.values()} == {
        "score",
        "replay",
        "guardrail",
        "parser",
        "time_budget",
        "candidate_budget",
    }


def test_probe_selection_prefers_uncertainty_reduction_per_cost() -> None:
    claims = initialize_evaluator_claims(_spec())
    ids = sorted(claims)
    probes = [
        EvaluatorProbeCandidate("expensive", (ids[0],), 2.0),
        EvaluatorProbeCandidate("cheap", (ids[1],), 0.5),
    ]

    selected = select_evaluator_probe(probes, claims)
    assert selected is not None
    assert selected.probe_id == "cheap"
    assert selected.information_gain_proxy > 0


def test_signal_updates_only_targeted_claim_and_preserves_research_only_material() -> None:
    claims = initialize_evaluator_claims(_spec())
    claim_id = sorted(claims)[0]
    untouched_id = sorted(claims)[1]
    probe = EvaluatorProbeCandidate("p1", (claim_id,), 1.0)
    signal = EvaluatorSignal(
        signal_id="s1",
        probe_id="p1",
        verdict=ProbeVerdict.SUPPORTED,
        evidence_refs=("evidence::s1",),
    )

    updated = update_evaluator_claims(claims, probe, signal)

    assert updated[claim_id].probability > claims[claim_id].probability
    assert updated[claim_id].support_count == 1
    assert updated[untouched_id] == claims[untouched_id]

    materials = evaluator_knowledge_materials(updated, [signal])
    material = next(item for item in materials if item.subject_ref == claim_id)
    assert material.kind == "EVALUATOR_SIGNAL"
    assert material.evidence_refs == ["evidence::s1"]
    assert material.independently_verified is False


def test_inconclusive_signal_does_not_invent_probability_change() -> None:
    claims = initialize_evaluator_claims(_spec())
    claim_id = sorted(claims)[0]
    probe = EvaluatorProbeCandidate("p1", (claim_id,), 1.0)
    signal = EvaluatorSignal("s1", "p1", ProbeVerdict.INCONCLUSIVE)

    updated = update_evaluator_claims(claims, probe, signal)
    assert updated[claim_id].probability == claims[claim_id].probability
    assert updated[claim_id].inconclusive_count == 1


def test_probe_validation_fails_closed() -> None:
    claims = initialize_evaluator_claims(_spec())
    claim_id = sorted(claims)[0]

    try:
        select_evaluator_probe(
            [EvaluatorProbeCandidate("bad", (claim_id,), 0.0)],
            claims,
        )
    except ValueError as exc:
        assert "cost_units must be positive" in str(exc)
    else:
        raise AssertionError("zero-cost evaluator probe must fail closed")
