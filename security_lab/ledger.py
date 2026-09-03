from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LedgerRecord:
    sequence: int
    record_type: str
    payload: dict[str, Any]
    previous_hash: str | None
    record_hash: str


def _record_hash(
    sequence: int,
    record_type: str,
    payload: dict[str, Any],
    previous_hash: str | None,
) -> str:
    canonical = json.dumps(
        {
            "sequence": sequence,
            "record_type": record_type,
            "payload": payload,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_record(
    *,
    sequence: int,
    record_type: str,
    payload: dict[str, Any],
    previous_hash: str | None,
) -> LedgerRecord:
    if sequence < 0:
        raise ValueError("sequence must be non-negative")
    if not record_type.strip():
        raise ValueError("record_type is required")
    digest = _record_hash(sequence, record_type, payload, previous_hash)
    return LedgerRecord(sequence, record_type, dict(payload), previous_hash, digest)


def verify_chain(records: Iterable[LedgerRecord]) -> str | None:
    previous: str | None = None
    expected_sequence = 0
    for record in records:
        if record.sequence != expected_sequence:
            raise ValueError(
                "ledger sequence mismatch: "
                f"expected {expected_sequence}, got {record.sequence}"
            )
        if record.previous_hash != previous:
            raise ValueError("ledger previous_hash mismatch")
        expected = _record_hash(
            record.sequence,
            record.record_type,
            record.payload,
            record.previous_hash,
        )
        if record.record_hash != expected:
            raise ValueError("ledger record hash mismatch")
        previous = record.record_hash
        expected_sequence += 1
    return previous


def append_record(
    path: str | Path,
    record_type: str,
    payload: dict[str, Any],
) -> LedgerRecord:
    ledger_path = Path(path)
    existing = load_records(ledger_path) if ledger_path.exists() else []
    previous_hash = verify_chain(existing)
    record = make_record(
        sequence=len(existing),
        record_type=record_type,
        payload=payload,
        previous_hash=previous_hash,
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(asdict(record), sort_keys=True, ensure_ascii=False)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(serialized + "\n")
    return record


def load_records(path: str | Path) -> list[LedgerRecord]:
    records: list[LedgerRecord] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(LedgerRecord(**json.loads(line)))
    return records
