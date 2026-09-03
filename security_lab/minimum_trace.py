from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import Trajectory

TraceSteps = tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class TraceEvaluation:
    """Research-only verdict for a replayed trace candidate."""

    successful: bool
    output_valid: bool = True
    score: float | None = None


@dataclass(frozen=True)
class MinimumWinningTrace:
    source_trajectory_id: str
    original_step_count: int
    winning_step_count: int
    removed_step_count: int
    replay_count: int
    minimum_steps: TraceSteps
    baseline: TraceEvaluation
    minimum_evaluation: TraceEvaluation


TraceEvaluator = Callable[[TraceSteps], TraceEvaluation]


def minimize_winning_trace(
    trajectory: Trajectory,
    evaluator: TraceEvaluator,
    *,
    minimum_prefix_steps: int = 0,
    require_output_valid: bool = True,
) -> MinimumWinningTrace:
    """Find the shortest successful prefix without assuming monotonic success.

    The function deliberately tests prefixes in ascending order instead of using
    binary search because agent/evaluator behavior may be non-monotonic across
    trace lengths. The caller owns the replay/evaluator implementation.
    """

    steps = tuple(trajectory.steps)
    if minimum_prefix_steps < 0:
        raise ValueError("minimum_prefix_steps must be non-negative")
    if minimum_prefix_steps > len(steps):
        raise ValueError("minimum_prefix_steps exceeds trajectory length")

    baseline = evaluator(steps)
    replay_count = 1
    if not _wins(baseline, require_output_valid=require_output_valid):
        raise ValueError("source trajectory does not satisfy the winning trace gate")

    for prefix_length in range(minimum_prefix_steps, len(steps) + 1):
        candidate = steps[:prefix_length]
        if prefix_length == len(steps):
            evaluation = baseline
        else:
            evaluation = evaluator(candidate)
            replay_count += 1
        if not _wins(evaluation, require_output_valid=require_output_valid):
            continue
        return MinimumWinningTrace(
            source_trajectory_id=trajectory.trajectory_id,
            original_step_count=len(steps),
            winning_step_count=prefix_length,
            removed_step_count=len(steps) - prefix_length,
            replay_count=replay_count,
            minimum_steps=candidate,
            baseline=baseline,
            minimum_evaluation=evaluation,
        )

    raise RuntimeError("winning prefix search exhausted despite a winning baseline")


def _wins(evaluation: TraceEvaluation, *, require_output_valid: bool) -> bool:
    if not evaluation.successful:
        return False
    return evaluation.output_valid or not require_output_valid
