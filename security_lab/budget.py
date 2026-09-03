from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetPlan:
    total_units: float
    evaluator_identification: float
    falsification: float
    optimization: float
    portfolio_validation: float


def allocate_budget(total_units: float) -> BudgetPlan:
    if total_units <= 0:
        raise ValueError("total_units must be positive")
    # Default allocation follows the lab's canonical research order:
    # identify -> falsify -> optimize survivors -> validate portfolio.
    return BudgetPlan(
        total_units=total_units,
        evaluator_identification=total_units * 0.25,
        falsification=total_units * 0.25,
        optimization=total_units * 0.35,
        portfolio_validation=total_units * 0.15,
    )
