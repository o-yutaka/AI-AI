from __future__ import annotations

import pytest

from security_lab.championship_freeze import freeze_championship_spec, verify_rehearsal


BASE = {
    "competition_slug": "ai-agent-security-multi-step-tool-attacks",
    "source_commit_sha": "1" * 40,
    "candidate_ids": ["candidate-b", "candidate-a"],
    "artifacts": {
        "runtime_contract": "a" * 64,
        "risk_spec": "b" * 64,
        "candidate_pack": "c" * 64,
    },
}


def test_freeze_is_order_stable() -> None:
    left = freeze_championship_spec(BASE)
    right = freeze_championship_spec(
        {
            **BASE,
            "candidate_ids": ["candidate-a", "candidate-b"],
            "artifacts": {
                "candidate_pack": "c" * 64,
                "risk_spec": "b" * 64,
                "runtime_contract": "a" * 64,
            },
        }
    )
    assert left.canonical_sha256 == right.canonical_sha256


def test_exact_rehearsal_passes() -> None:
    freeze = freeze_championship_spec(BASE)
    verdict = verify_rehearsal(freeze, BASE)
    assert verdict.verdict == "PASS"
    assert verdict.reason_codes == ()


def test_candidate_or_artifact_drift_rejects() -> None:
    freeze = freeze_championship_spec(BASE)
    drifted = {
        **BASE,
        "candidate_ids": ["candidate-a", "candidate-c"],
        "artifacts": {**BASE["artifacts"], "risk_spec": "d" * 64},
    }
    verdict = verify_rehearsal(freeze, drifted)
    assert verdict.verdict == "REJECTED"
    assert "candidate_set_mismatch" in verdict.reason_codes
    assert "artifact_binding_mismatch" in verdict.reason_codes
    assert "canonical_freeze_mismatch" in verdict.reason_codes


def test_invalid_digest_fails_closed() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        freeze_championship_spec({**BASE, "artifacts": {"risk_spec": "abc"}})


def test_duplicate_candidates_fail_closed() -> None:
    with pytest.raises(ValueError, match="unique"):
        freeze_championship_spec({**BASE, "candidate_ids": ["a", "a"]})
