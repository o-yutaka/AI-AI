from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateProfile:
    candidate_id: str
    family_id: str
    expected_score: float
    survival_probability: float
    throughput: float
    failure_cluster: str

    @property
    def expected_value(self) -> float:
        return self.expected_score * self.survival_probability * self.throughput


def select_diverse_portfolio(
    candidates: list[CandidateProfile],
    limit: int,
) -> list[CandidateProfile]:
    if limit < 1:
        return []
    ranked = sorted(candidates, key=lambda item: (-item.expected_value, item.candidate_id))
    selected: list[CandidateProfile] = []
    seen_clusters: set[str] = set()

    for candidate in ranked:
        if candidate.failure_cluster in seen_clusters:
            continue
        selected.append(candidate)
        seen_clusters.add(candidate.failure_cluster)
        if len(selected) == limit:
            return selected

    for candidate in ranked:
        if candidate in selected:
            continue
        selected.append(candidate)
        if len(selected) == limit:
            break
    return selected
