from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class FrozenArtifact:
    name: str
    sha256: str


@dataclass(frozen=True)
class ChampionshipFreeze:
    schema_version: str
    competition_slug: str
    source_commit_sha: str
    candidate_ids: tuple[str, ...]
    artifacts: tuple[FrozenArtifact, ...]
    canonical_sha256: str


@dataclass(frozen=True)
class RehearsalVerdict:
    verdict: str
    reason_codes: tuple[str, ...]
    expected_sha256: str
    observed_sha256: str


def freeze_championship_spec(raw: Mapping[str, Any]) -> ChampionshipFreeze:
    competition_slug = _required_string(raw, "competition_slug")
    source_commit_sha = _sha40(_required_string(raw, "source_commit_sha"), "source_commit_sha")
    candidate_ids = tuple(sorted(_unique_strings(raw.get("candidate_ids"), "candidate_ids")))
    if not candidate_ids:
        raise ValueError("candidate_ids must not be empty")

    artifacts_raw = raw.get("artifacts")
    if not isinstance(artifacts_raw, Mapping) or not artifacts_raw:
        raise ValueError("artifacts must be a non-empty object")
    artifacts = tuple(
        FrozenArtifact(str(name), _sha256(str(value), f"artifacts.{name}"))
        for name, value in sorted(artifacts_raw.items(), key=lambda item: str(item[0]))
    )

    payload = {
        "schema_version": "championship-freeze.v1",
        "competition_slug": competition_slug,
        "source_commit_sha": source_commit_sha,
        "candidate_ids": list(candidate_ids),
        "artifacts": {item.name: item.sha256 for item in artifacts},
    }
    return ChampionshipFreeze(
        schema_version="championship-freeze.v1",
        competition_slug=competition_slug,
        source_commit_sha=source_commit_sha,
        candidate_ids=candidate_ids,
        artifacts=artifacts,
        canonical_sha256=_canonical_sha256(payload),
    )


def verify_rehearsal(freeze: ChampionshipFreeze, observed: Mapping[str, Any]) -> RehearsalVerdict:
    observed_freeze = freeze_championship_spec(observed)
    reasons: list[str] = []
    if freeze.competition_slug != observed_freeze.competition_slug:
        reasons.append("competition_mismatch")
    if freeze.source_commit_sha != observed_freeze.source_commit_sha:
        reasons.append("source_commit_mismatch")
    if freeze.candidate_ids != observed_freeze.candidate_ids:
        reasons.append("candidate_set_mismatch")
    if freeze.artifacts != observed_freeze.artifacts:
        reasons.append("artifact_binding_mismatch")
    if freeze.canonical_sha256 != observed_freeze.canonical_sha256:
        reasons.append("canonical_freeze_mismatch")
    return RehearsalVerdict(
        verdict="PASS" if not reasons else "REJECTED",
        reason_codes=tuple(reasons),
        expected_sha256=freeze.canonical_sha256,
        observed_sha256=observed_freeze.canonical_sha256,
    )


def freeze_payload(freeze: ChampionshipFreeze) -> dict[str, Any]:
    return {
        "schema_version": freeze.schema_version,
        "competition_slug": freeze.competition_slug,
        "source_commit_sha": freeze.source_commit_sha,
        "candidate_ids": list(freeze.candidate_ids),
        "artifacts": {item.name: item.sha256 for item in freeze.artifacts},
        "canonical_sha256": freeze.canonical_sha256,
    }


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _unique_strings(value: Any, name: str) -> Sequence[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{name} must be an array of non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must contain unique values")
    return value


def _sha256(value: str, name: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _sha40(value: str, name: str) -> str:
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase 40-character git SHA")
    return value
