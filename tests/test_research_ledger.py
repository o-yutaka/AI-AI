import json

import pytest

from security_lab import append_record, load_records, verify_chain


def test_ledger_appends_and_verifies(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    first = append_record(path, "probe", {"probe_id": "p1"})
    second = append_record(path, "observation", {"observation_id": "o1"})

    records = load_records(path)
    assert len(records) == 2
    assert records[0] == first
    assert records[1] == second
    assert second.previous_hash == first.record_hash
    assert verify_chain(records) == second.record_hash


def test_ledger_detects_tampering(tmp_path) -> None:
    path = tmp_path / "ledger.jsonl"
    append_record(path, "probe", {"probe_id": "p1"})
    raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    raw[0]["payload"]["probe_id"] = "tampered"
    path.write_text("\n".join(json.dumps(item) for item in raw) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="record hash mismatch"):
        verify_chain(load_records(path))
