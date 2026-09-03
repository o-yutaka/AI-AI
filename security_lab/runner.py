from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .models import EnvironmentIdentity, Hypothesis, Probe, ProbeVerdict, Split
from .probe import compile_probe
from .replay import ReplayResult, replay_probe


@dataclass(frozen=True)
class ExperimentCase:
    hypothesis: Hypothesis
    split: Split
    instance_id: str
    payload: dict[str, object]
    environment: EnvironmentIdentity
    budget_cost: float = 1.0


@dataclass(frozen=True)
class ExperimentRun:
    case: ExperimentCase
    probe: Probe
    replay: ReplayResult


CaseExecutor = Callable[
    [Probe, ExperimentCase],
    tuple[str, ProbeVerdict, list[dict[str, Any]], dict[str, float]],
]


def run_cases(
    cases: Iterable[ExperimentCase],
    *,
    execute: CaseExecutor,
) -> list[ExperimentRun]:
    """Run model-neutral research cases through the canonical replay boundary.

    The runner knows runtime identity and split, but never BLACK authority,
    leaderboard authority, or adoption/promotion state.
    """
    runs: list[ExperimentRun] = []
    for case in cases:
        payload = {
            "instance_id": case.instance_id,
            **case.payload,
        }
        probe = compile_probe(
            case.hypothesis,
            payload,
            split=case.split,
            budget_cost=case.budget_cost,
        )
        replay = replay_probe(
            probe,
            case.environment,
            lambda current_probe: execute(current_probe, case),
        )
        runs.append(ExperimentRun(case=case, probe=probe, replay=replay))
    return runs
