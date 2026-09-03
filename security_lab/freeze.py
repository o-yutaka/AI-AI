from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CandidateFreeze:
    freeze_id: str
    candidate_ids: tuple[str, ...]
    content_hash: str


def freeze_candidates(candidate_ids: Iterable[str]) -> CandidateFreeze:
    normalized = tuple(sorted(set(candidate_ids)))
    canonical = json.dumps(normalized, separators=(",", ":"))
    content_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return CandidateFreeze(f"freeze-{content_hash[:24]}", normalized, content_hash)
