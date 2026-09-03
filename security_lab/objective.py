from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class ObjectiveResult:
    objective_id: str
    score: float
    passed: bool
    metrics: Mapping[str, float]


class Objective(Protocol):
    objective_id: str
    def evaluate(self, metrics: Mapping[str, float]) -> ObjectiveResult: ...


@dataclass(frozen=True)
class WeightedObjective:
    objective_id: str
    weights: Mapping[str, float]
    threshold: float

    def evaluate(self, metrics: Mapping[str, float]) -> ObjectiveResult:
        score = sum(float(metrics.get(name, 0.0)) * weight for name, weight in self.weights.items())
        return ObjectiveResult(self.objective_id, score, score >= self.threshold, dict(metrics))
