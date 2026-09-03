from __future__ import annotations

from dataclasses import dataclass

from .models import Hypothesis, Observation, Probe, ProbeVerdict


@dataclass(frozen=True)
class HypothesisBelief:
    hypothesis_id: str
    probability: float


def initial_beliefs(hypotheses: list[Hypothesis]) -> dict[str, HypothesisBelief]:
    return {
        item.hypothesis_id: HypothesisBelief(item.hypothesis_id, _clamp_probability(item.prior))
        for item in hypotheses
    }


def update_belief(
    belief: HypothesisBelief,
    observation: Observation,
    *,
    supported_likelihood_ratio: float = 4.0,
    refuted_likelihood_ratio: float = 0.25,
    blocked_likelihood_ratio: float = 0.8,
) -> HypothesisBelief:
    if observation.verdict is ProbeVerdict.INCONCLUSIVE:
        return belief
    likelihood_ratio = {
        ProbeVerdict.SUPPORTED: supported_likelihood_ratio,
        ProbeVerdict.REFUTED: refuted_likelihood_ratio,
        ProbeVerdict.BLOCKED: blocked_likelihood_ratio,
    }[observation.verdict]
    prior = _clamp_probability(belief.probability)
    prior_odds = prior / (1.0 - prior)
    posterior_odds = prior_odds * likelihood_ratio
    posterior = posterior_odds / (1.0 + posterior_odds)
    return HypothesisBelief(belief.hypothesis_id, _clamp_probability(posterior))


def select_next_probe(
    probes: list[Probe],
    beliefs: dict[str, HypothesisBelief],
    completed_probe_ids: set[str] | None = None,
) -> Probe | None:
    completed = completed_probe_ids or set()
    available = [probe for probe in probes if probe.probe_id not in completed]
    if not available:
        return None

    def priority(probe: Probe) -> tuple[float, str]:
        probability = beliefs.get(probe.hypothesis_id, HypothesisBelief(probe.hypothesis_id, 0.5)).probability
        uncertainty = 1.0 - abs(2.0 * probability - 1.0)
        cost = max(probe.budget_cost, 1e-9)
        return (-(uncertainty / cost), probe.probe_id)

    return sorted(available, key=priority)[0]


def _clamp_probability(value: float) -> float:
    return max(1e-6, min(1.0 - 1e-6, value))
