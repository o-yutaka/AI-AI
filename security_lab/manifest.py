from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentManifest:
    experiment_id: str
    competition_slug: str
    model_id: str
    compiler_id: str
    runtime_id: str
    split: str
    seed: int
    tool_surface_hash: str
    evaluator_hash: str
    dataset_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        payload = {
            "experiment_id": self.experiment_id,
            "competition_slug": self.competition_slug,
            "model_id": self.model_id,
            "compiler_id": self.compiler_id,
            "runtime_id": self.runtime_id,
            "split": self.split,
            "seed": self.seed,
            "tool_surface_hash": self.tool_surface_hash,
            "evaluator_hash": self.evaluator_hash,
            "dataset_hash": self.dataset_hash,
            "metadata": self.metadata,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
