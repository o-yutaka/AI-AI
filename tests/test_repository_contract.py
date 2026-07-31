from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "docs" / "assets" / "proof"


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_required_public_repository_files_exist() -> None:
    for path in (
        "LICENSE",
        "SECURITY.md",
        "CHANGELOG.md",
        ".env.example",
        "requirements.lock.txt",
        "requirements.runtime.lock.txt",
        "web/package-lock.json",
        "docs/assets/proof/visual-proof-manifest.json",
        "docs/assets/proof/ai-agent-control-plane-proof.gif",
    ):
        assert (ROOT / path).is_file(), path
        assert (ROOT / path).stat().st_size > 0, path


def test_readme_routes_reviewers_to_live_and_visual_proof() -> None:
    readme = text("README.md")

    assert "raw.githack.com/o-yutaka/AI-AI/main/docs/live-demo.html" in readme
    assert "docs/assets/proof/ai-agent-control-plane-proof.gif" in readme
    assert "visual-proof-manifest.json" in readme
    assert "PUBLIC SIMULATION" in readme.upper()
    assert "execution count `0`" in readme
    assert "execution count `1`" in readme
    assert "424" not in readme


def test_committed_proof_manifest_meets_promotion_gate() -> None:
    manifest = json.loads((PROOF / "visual-proof-manifest.json").read_text())
    verification = manifest["verification"]

    assert verification["different_run_ids_same_input"] is True
    assert verification["duplicate_execution_count"] == 1
    assert verification["blocked_execution_count"] == 0
    assert verification["conflict_execution_count"] == 0
    assert verification["approved_execution_count"] == 1

    assets = {item["file"]: item for item in manifest["assets"]}
    minimums = {
        "ai-agent-control-plane-desktop-waiting.jpg": (1440, 1000),
        "ai-agent-control-plane-desktop-approved.jpg": (1440, 1000),
        "ai-agent-control-plane-desktop-blocked.jpg": (1440, 1000),
        "ai-agent-control-plane-desktop-idempotency.jpg": (1440, 1000),
        "ai-agent-control-plane-mobile-waiting.jpg": (390, 844),
        "ai-agent-control-plane-proof.gif": (640, 500),
    }
    for name, (width, height) in minimums.items():
        assert assets[name]["width"] >= width
        assert assets[name]["height"] >= height
        assert assets[name]["bytes"] > 10_000
        assert (PROOF / name).is_file()


def test_all_delivery_paths_use_committed_locks() -> None:
    ci = text(".github/workflows/ci.yml")
    pages = text(".github/workflows/pages.yml")
    api_docker = text("Dockerfile")
    web_docker = text("web/Dockerfile")

    assert "pip install -r requirements.lock.txt" in ci
    assert "npm ci" in ci
    assert "requirements.runtime.lock.txt" in api_docker
    assert "pip install -r requirements.runtime.lock.txt" in api_docker
    assert "COPY package.json package-lock.json" in web_docker
    assert "npm ci" in web_docker
    assert "npm ci" in pages
    assert "npm install --no-audit" not in ci
    assert "npm install --no-audit" not in pages


def test_proof_workflow_is_validation_only() -> None:
    workflow = text(".github/workflows/generate-proof-assets.yml")

    assert "pull_request:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "contents: read" in workflow
    assert "commit-generated" not in workflow
    assert "git push" not in workflow
    assert "feature/portfolio-proof-complete-20260801" not in workflow


def test_deployment_truth_is_not_overstated() -> None:
    status = json.loads(text("docs/live-status.json"))
    readme = text("README.md")

    if status.get("pages_verification_result") != "success":
        assert "not described as live" in readme
        assert "repository-level Pages is enabled" in readme
