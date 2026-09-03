from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

from .budget import BudgetPlan, allocate_budget
from .competition import CompetitionSpec
from .dataset import FrozenDataset, freeze_dataset
from .reproducibility import stable_hash
from .runtime_matrix import RuntimeMatrix, build_runtime_matrix


@dataclass(frozen=True)
class ResearchPlan:
    plan_id: str
    competition: CompetitionSpec
    dataset: FrozenDataset
    budget: BudgetPlan
    runtime_matrix: RuntimeMatrix
    canonical_sha256: str


def build_research_plan(
    *,
    competition: CompetitionSpec,
    dataset_id: str,
    source_revision: str,
    instance_ids: Iterable[str],
    total_budget_units: float,
    model_ids: Iterable[str],
    runtime_ids: Iterable[str],
    compiler_ids: Iterable[str],
    quantizations: Iterable[str],
) -> ResearchPlan:
    dataset = freeze_dataset(dataset_id, source_revision, instance_ids)
    budget = allocate_budget(total_budget_units)
    runtime_matrix = build_runtime_matrix(
        model_ids=model_ids,
        runtime_ids=runtime_ids,
        compiler_ids=compiler_ids,
        quantizations=quantizations,
    )
    core = {
        "competition": asdict(competition),
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "source_revision": dataset.source_revision,
            "manifest_sha256": dataset.manifest_sha256,
            "instances": [
                {
                    "instance_id": item.instance_id,
                    "split": item.split.value,
                    "identity_hash": item.identity_hash,
                }
                for item in dataset.instances
            ],
        },
        "budget": asdict(budget),
        "runtime_matrix": [asdict(item) for item in runtime_matrix.variants],
    }
    digest = stable_hash(core)
    return ResearchPlan(
        plan_id=f"research-plan-{digest[:24]}",
        competition=competition,
        dataset=dataset,
        budget=budget,
        runtime_matrix=runtime_matrix,
        canonical_sha256=digest,
    )
