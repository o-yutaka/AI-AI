from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluatorSpec:
    evaluator_id: str
    score_predicates: tuple[str, ...]
    replay_semantics: tuple[str, ...]
    guardrail_classes: tuple[str, ...]
    parser_constraints: tuple[str, ...]
    time_budget_seconds: float | None = None
    candidate_budget: int | None = None


@dataclass(frozen=True)
class EvaluatorDimension:
    dimension: str
    claims: tuple[str, ...]


def decompose_evaluator(spec: EvaluatorSpec) -> tuple[EvaluatorDimension, ...]:
    dimensions = [
        EvaluatorDimension("score", tuple(sorted(spec.score_predicates))),
        EvaluatorDimension("replay", tuple(sorted(spec.replay_semantics))),
        EvaluatorDimension("guardrail", tuple(sorted(spec.guardrail_classes))),
        EvaluatorDimension("parser", tuple(sorted(spec.parser_constraints))),
    ]
    if spec.time_budget_seconds is not None:
        dimensions.append(
            EvaluatorDimension(
                "time_budget",
                (f"seconds={spec.time_budget_seconds:g}",),
            )
        )
    if spec.candidate_budget is not None:
        dimensions.append(
            EvaluatorDimension(
                "candidate_budget",
                (f"count={spec.candidate_budget}",),
            )
        )
    return tuple(dimensions)
