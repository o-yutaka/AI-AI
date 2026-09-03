from security_lab.belief import HypothesisBelief, select_next_probe, update_belief
from security_lab.models import Hypothesis, Observation, ProbeVerdict
from security_lab.primitives import AttackPrimitive, CompositionKind, PrimitiveComposition
from security_lab.probe import compile_probe


def test_supported_observation_increases_belief() -> None:
    belief = HypothesisBelief("h1", 0.5)
    observation = Observation("o1", "h1::probe", "signal", ProbeVerdict.SUPPORTED)
    updated = update_belief(belief, observation)
    assert updated.probability > belief.probability


def test_scheduler_prefers_uncertain_low_cost_probe() -> None:
    h1 = Hypothesis("h1", "a", "x", "not x", "signal", prior=0.5)
    h2 = Hypothesis("h2", "b", "y", "not y", "signal", prior=0.5)
    expensive = compile_probe(h1, {"case": 1}, budget_cost=4.0)
    cheap = compile_probe(h2, {"case": 2}, budget_cost=1.0)
    selected = select_next_probe(
        [expensive, cheap],
        {"h1": HypothesisBelief("h1", 0.5), "h2": HypothesisBelief("h2", 0.5)},
    )
    assert selected == cheap


def test_primitive_composition_preserves_surface_and_operator_identity() -> None:
    primitive = AttackPrimitive("p1", "family-a", "tool-call", "sequence-shape", "known schema", "parser signal")
    composition = PrimitiveComposition("c1", CompositionKind.SEQUENTIAL, (primitive.primitive_id,))
    assert composition.primitive_ids == ("p1",)
