from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .budget import BudgetPlan


class BudgetStage(StrEnum):
    EVALUATOR_IDENTIFICATION = "evaluator_identification"
    FALSIFICATION = "falsification"
    OPTIMIZATION = "optimization"
    PORTFOLIO_VALIDATION = "portfolio_validation"


@dataclass
class BudgetLedger:
    plan: BudgetPlan
    spent: dict[BudgetStage, float] = field(default_factory=dict)

    def limit(self, stage: BudgetStage) -> float:
        return float(getattr(self.plan, stage.value))

    def used(self, stage: BudgetStage) -> float:
        return self.spent.get(stage, 0.0)

    def remaining(self, stage: BudgetStage) -> float:
        return self.limit(stage) - self.used(stage)

    def charge(self, stage: BudgetStage, units: float) -> None:
        if units < 0:
            raise ValueError("budget charge must be non-negative")
        next_used = self.used(stage) + units
        if next_used > self.limit(stage) + 1e-12:
            raise ValueError(
                f"research budget exceeded for {stage.value}: "
                f"limit={self.limit(stage)}, attempted={next_used}"
            )
        self.spent[stage] = next_used
