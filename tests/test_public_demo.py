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


def test_public_demo_exposes_the_reviewable_workflow() -> None:
    html = DEMO.read_text(encoding="utf-8")

    for element_id in (
        "lowRisk",
        "highRisk",
        "approve",
        "reject",
        "policyChecks",
        "rejectedActions",
        "events",
        "result",
        "identity",
    ):
        assert f'id="{element_id}"' in html

    assert 'status: waiting ? "waiting_approval" : "completed"' in html
    assert 'decision === "approve"' in html
    assert 'external_side_effect: false' in html
    assert 'provider: "openai-compatible"' in html
    assert 'adapter: "http_json"' in html
