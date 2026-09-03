from __future__ import annotations

from dataclasses import dataclass

from .portfolio import CandidateProfile


@dataclass(frozen=True)
class FailureProfile:
    candidate_id: str
    failures: tuple[bool, ...]


@dataclass(frozen=True)
class FailureCorrelationGraph:
    candidate_ids: tuple[str, ...]
    context_count: int
    pairwise_jaccard: dict[tuple[str, str], float]

    def correlation(self, left: str, right: str) -> float:
        if left == right:
            if left not in self.candidate_ids:
                raise KeyError(left)
            return 1.0
        key = tuple(sorted((left, right)))
        try:
            return self.pairwise_jaccard[key]
        except KeyError as exc:
            raise KeyError(f"unknown candidate pair: {left}, {right}") from exc


def build_failure_correlation_graph(
    profiles: list[FailureProfile],
) -> FailureCorrelationGraph:
    if not profiles:
        return FailureCorrelationGraph((), 0, {})

    candidate_ids = [item.candidate_id for item in profiles]
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("failure profile candidate IDs must be unique")

    context_count = len(profiles[0].failures)
    if any(len(item.failures) != context_count for item in profiles):
        raise ValueError("failure profiles must use the same ordered contexts")

    ordered = sorted(profiles, key=lambda item: item.candidate_id)
    pairwise: dict[tuple[str, str], float] = {}
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            pairwise[(left.candidate_id, right.candidate_id)] = _failure_jaccard(
                left.failures,
                right.failures,
            )

    return FailureCorrelationGraph(
        candidate_ids=tuple(item.candidate_id for item in ordered),
        context_count=context_count,
        pairwise_jaccard=pairwise,
    )


def select_correlation_diverse_portfolio(
    candidates: list[CandidateProfile],
    graph: FailureCorrelationGraph,
    limit: int,
    *,
    correlation_penalty: float = 1.0,
) -> list[CandidateProfile]:
    """Greedily trade candidate value against observed shared failure modes."""

    if limit < 1:
        return []
    if not 0.0 <= correlation_penalty <= 1.0:
        raise ValueError("correlation_penalty must be between 0 and 1")
    if len({item.candidate_id for item in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")

    missing = sorted(
        item.candidate_id
        for item in candidates
        if item.candidate_id not in graph.candidate_ids
    )
    if missing:
        raise ValueError(
            "failure correlation graph is missing candidates: " + ",".join(missing)
        )

    remaining = list(candidates)
    selected: list[CandidateProfile] = []
    while remaining and len(selected) < limit:
        chosen = min(
            remaining,
            key=lambda item: (
                -_diversified_value(
                    item,
                    selected,
                    graph,
                    correlation_penalty=correlation_penalty,
                ),
                item.candidate_id,
            ),
        )
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def _diversified_value(
    candidate: CandidateProfile,
    selected: list[CandidateProfile],
    graph: FailureCorrelationGraph,
    *,
    correlation_penalty: float,
) -> float:
    if not selected:
        return candidate.expected_value
    maximum_correlation = max(
        graph.correlation(candidate.candidate_id, item.candidate_id)
        for item in selected
    )
    diversity_factor = 1.0 - correlation_penalty * maximum_correlation
    return candidate.expected_value * diversity_factor


def _failure_jaccard(left: tuple[bool, ...], right: tuple[bool, ...]) -> float:
    intersection = sum(a and b for a, b in zip(left, right, strict=True))
    union = sum(a or b for a, b in zip(left, right, strict=True))
    return 0.0 if union == 0 else intersection / union
