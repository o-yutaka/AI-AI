from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .models import EnvironmentIdentity, Observation, Probe, ProbeVerdict, Trajectory


@dataclass(frozen=True)
class ReplayResult:
    observation: Observation
    trajectory: Trajectory


ReplayExecutor = Callable[[Probe], tuple[str, ProbeVerdict, list[dict[str, Any]], dict[str, float]]]


def replay_probe(
    probe: Probe,
    environment: EnvironmentIdentity,
    executor: ReplayExecutor,
) -> ReplayResult:
    started = perf_counter()
    observable, verdict, steps, metrics = executor(probe)
    latency_ms = (perf_counter() - started) * 1000.0
    completed = verdict is not ProbeVerdict.BLOCKED
    trajectory = Trajectory(
        trajectory_id=f"trajectory::{probe.probe_id}",
        probe_id=probe.probe_id,
        environment=environment,
        steps=tuple(steps),
        token_count=int(metrics.get("token_count", 0)),
        latency_ms=float(metrics.get("latency_ms", latency_ms)),
        completed=completed,
    )
    observation = Observation(
        observation_id=f"observation::{probe.probe_id}",
        probe_id=probe.probe_id,
        observable=observable,
        verdict=verdict,
        metrics={key: float(value) for key, value in metrics.items()},
        evidence_refs=(trajectory.trajectory_id,),
    )
    return ReplayResult(observation=observation, trajectory=trajectory)
