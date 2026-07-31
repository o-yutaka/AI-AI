from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "docs" / "live-demo.html"


def test_public_demo_is_self_contained_and_network_disabled() -> None:
    html = DEMO.read_text(encoding="utf-8")

    assert "AI Agent Control Plane" in html
    assert "connect-src 'none'" in html
    assert "<script src=" not in html
    assert '<link rel="stylesheet"' not in html
    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "WebSocket" not in html


def test_public_demo_exposes_all_proof_scenarios() -> None:
    html = DEMO.read_text(encoding="utf-8")

    for element_id in (
        "lowRisk",
        "highRisk",
        "blockedRisk",
        "replaySame",
        "replayConflict",
        "approve",
        "reject",
        "policyChecks",
        "rejectedActions",
        "events",
        "result",
        "identity",
        "metricExecutions",
        "metricReplay",
    ):
        assert f'id="{element_id}"' in html

    assert "PUBLIC SIMULATION" in html
    assert "Provider generation and tool execution are simulated" in html
    assert 'crypto.subtle.digest("SHA-256"' in html
    assert "canonical_input_excludes_run_id:true" in html
    assert "idempotency_replay" in html
    assert "idempotency_conflict" in html
    assert "no_second_execution:true" in html
    assert "run_blocked" in html
    assert "not_in_current_contract" in html
    assert "missing_permissions" in html
    assert "missing_evidence_for_high_risk_action" in html
    assert "unregistered_tool_operation" in html
    assert "external_side_effect:false" in html
