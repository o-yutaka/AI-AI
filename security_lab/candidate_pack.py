from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CandidateRecord:
    candidate_id: str
    family: str
    compiler_id: str
    payload_sha256: str
    failure_cluster: str
    expected_value: float
    survival_probability: float
    throughput: float


@dataclass(frozen=True)
class CandidatePackage:
    package_id: str
    records: tuple[CandidateRecord, ...]
    canonical_sha256: str


def package_candidates(records: Iterable[CandidateRecord]) -> CandidatePackage:
    normalized = tuple(sorted(records, key=lambda item: item.candidate_id))
    if len({item.candidate_id for item in normalized}) != len(normalized):
        raise ValueError("candidate IDs must be unique")
    payload = json.dumps(
        [asdict(item) for item in normalized],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return CandidatePackage(
        package_id=f"candidate-package-{digest[:24]}",
        records=normalized,
        canonical_sha256=digest,
    )
