from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

from .budget_ledger import BudgetLedger, BudgetStage
from .leakage import ResearchPurpose, assert_split_allowed
from .ledger import append_record
from .runner import (
    CaseExecutor,
    ExperimentCase,
    ExperimentRun,
    run_cases,
)


_STAGE_BY_PURPOSE: dict[ResearchPurpose, BudgetStage] = {
    ResearchPurpose.DISCOVERY: BudgetStage.EVALUATOR_IDENTIFICATION,
    ResearchPurpose.FALSIFICATION: BudgetStage.FALSIFICATION,
    ResearchPurpose.OPTIMIZATION: BudgetStage.OPTIMIZATION,
    ResearchPurpose.VALIDATION: BudgetStage.PORTFOLIO_VALIDATION,
    ResearchPurpose.ADVERSARIAL_VALIDATION: BudgetStage.PORTFOLIO_VALIDATION,
}


@dataclass
class ResearchSession:
    budget: BudgetLedger
    ledger_path: Path | None = None

    def run(
        self,
        purpose: ResearchPurpose,
        cases: Iterable[ExperimentCase],
        *,
        execute: CaseExecutor,
    ) -> list[ExperimentRun]:
        stage = _STAGE_BY_PURPOSE[purpose]
        results: list[ExperimentRun] = []
        for case in cases:
            assert_split_allowed(purpose, case.split)
            self.budget.charge(stage, case.budget_cost)
            run = run_cases([case], execute=execute)[0]
            results.append(run)
            if self.ledger_path is not None:
                append_record(
                    self.ledger_path,
                    "experiment_run",
                    {
                        "purpose": purpose.value,
                        "budget_stage": stage.value,
                        "budget_units": case.budget_cost,
                        "instance_id": case.instance_id,
                        "probe_id": run.probe.probe_id,
                        "split": run.probe.split.value,
                        "environment": asdict(case.environment),
                        "observation_id": run.replay.observation.observation_id,
                        "trajectory_id": run.replay.trajectory.trajectory_id,
                        "verdict": run.replay.observation.verdict.value,
                        "metrics": run.replay.observation.metrics,
                    },
                )
        return results
