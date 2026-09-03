from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .models import Hypothesis, Probe, Split
from .probe import compile_minimal_falsification_probe
from .replay import ReplayResult, replay_probe


@dataclass(frozen=True)
class ExperimentCase:
    hypothesis: Hypothesis
    split: Split
    instance_id: str
    payload: str


@dataclass(frozen=True)
class ExperimentRun:
    case: ExperimentCase
    probe: Probe
    replay: ReplayResult


def run_cases(
    cases: Iterable[ExperimentCase],
    *,
    execute: Callable[[Probe, ExperimentCase], object],
) -> list[ExperimentRun]:
    """Run model-neutral research cases through one replay boundary.

    The runner intentionally does not know BLACK, leaderboard state, or any
    adoption/promotion concept. It only compiles falsification probes, executes
    them, and returns reproducible replay records.
    """
    runs: list[ExperimentRun] = []
    for case in cases:
        probe = compile_minimal_falsification_probe(case.hypothesis)
        replay = replay_probe(
            probe,
            split=case.split,
            execute=lambda: execute(probe, case),
            source=f"instance:{case.instance_id}",
        )
        runs.append(ExperimentRun(case=case, probe=probe, replay=replay))
    return runs
