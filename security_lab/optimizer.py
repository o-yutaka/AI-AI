from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class OptimizationCandidate:
    candidate_id: str
    payload: Mapping[str, Any]
    parent_id: str | None = None
    lineage: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptimizationObservation:
    candidate_id: str
    score: float
    passed: bool = False
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class OptimizationRequest:
    frontier: tuple[OptimizationCandidate, ...]
    history: tuple[OptimizationObservation, ...] = ()
    proposal_limit: int = 1


class Optimizer(Protocol):
    """Proposal-only research optimizer.

    Implementations may generate candidate research variants, but they do not
    evaluate candidates and carry no research or BLACK authority.
    """

    optimizer_id: str

    def propose(self, request: OptimizationRequest) -> tuple[OptimizationCandidate, ...]: ...


NeighborhoodFunction = Callable[[OptimizationCandidate], Iterable[OptimizationCandidate]]


@dataclass(frozen=True)
class DeterministicNeighborhoodOptimizer:
    optimizer_id: str
    neighborhood: NeighborhoodFunction

    def propose(self, request: OptimizationRequest) -> tuple[OptimizationCandidate, ...]:
        if request.proposal_limit < 1:
            raise ValueError("proposal_limit must be positive")
        if not request.frontier:
            raise ValueError("optimizer requires at least one frontier candidate")

        seen = {candidate.candidate_id for candidate in request.frontier}
        seen.update(item.candidate_id for item in request.history)
        proposals: dict[str, OptimizationCandidate] = {}
        for parent in sorted(request.frontier, key=lambda item: item.candidate_id):
            for candidate in self.neighborhood(parent):
                if candidate.candidate_id in seen or candidate.candidate_id in proposals:
                    continue
                proposals[candidate.candidate_id] = candidate

        return tuple(proposals[key] for key in sorted(proposals)[: request.proposal_limit])


def select_frontier(
    candidates: Sequence[OptimizationCandidate],
    observations: Sequence[OptimizationObservation],
    *,
    limit: int,
) -> tuple[OptimizationCandidate, ...]:
    if limit < 1:
        raise ValueError("limit must be positive")
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    if len(by_id) != len(candidates):
        raise ValueError("candidate ids must be unique")

    latest: dict[str, OptimizationObservation] = {}
    for observation in observations:
        if observation.candidate_id not in by_id:
            raise ValueError(f"observation references unknown candidate: {observation.candidate_id}")
        latest[observation.candidate_id] = observation

    ranked = sorted(
        by_id.values(),
        key=lambda candidate: (
            not latest.get(candidate.candidate_id, OptimizationObservation(candidate.candidate_id, float("-inf"))).passed,
            -latest.get(candidate.candidate_id, OptimizationObservation(candidate.candidate_id, float("-inf"))).score,
            candidate.candidate_id,
        ),
    )
    return tuple(ranked[:limit])
