from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image
from playwright.sync_api import Page, sync_playwright


def read_json(page: Page, selector: str) -> dict[str, Any]:
    return json.loads(page.locator(selector).inner_text())


def click_and_wait(page: Page, selector: str, status: str) -> None:
    page.locator(selector).click()
    page.locator("#statusText").wait_for(state="visible")
    page.wait_for_function(
        "expected => document.querySelector('#statusText')?.textContent?.trim() === expected",
        status,
    )


def verify_demo(page: Page, base_url: str) -> dict[str, Any]:
    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#lowRisk", "COMPLETED")
    first_identity = read_json(page, "#identity")
    first_run_id = first_identity["run_id"]
    first_fingerprint = first_identity["request_fingerprint"]
    assert first_identity["execution_count"] == 1
    assert first_identity["canonical_input_excludes_run_id"] is True

    page.locator("#reset").click()
    click_and_wait(page, "#lowRisk", "COMPLETED")
    second_identity = read_json(page, "#identity")
    assert second_identity["run_id"] != first_run_id
    assert second_identity["request_fingerprint"] == first_fingerprint

    click_and_wait(page, "#replaySame", "COMPLETED")
    replay_identity = read_json(page, "#identity")
    assert replay_identity["run_id"] == second_identity["run_id"]
    assert replay_identity["execution_count"] == 1
    assert replay_identity["idempotency_replayed"] is True
    assert page.locator("#metricReplay").inner_text() == "REUSED"

    click_and_wait(page, "#blockedRisk", "BLOCKED")
    blocked_identity = read_json(page, "#identity")
    blocked_text = page.locator("#rejectedActions").inner_text()
    assert blocked_identity["execution_count"] == 0
    for reason in (
        "not_in_current_contract",
        "missing_permissions",
        "missing_evidence_for_high_risk_action",
        "unregistered_tool_operation",
    ):
        assert reason in blocked_text

    click_and_wait(page, "#replayConflict", "BLOCKED")
    conflict = read_json(page, "#result")
    assert conflict["error_type"] == "IdempotencyConflictError"
    conflict_identity = read_json(page, "#identity")
    assert conflict_identity["execution_count"] == 0

    click_and_wait(page, "#highRisk", "WAITING APPROVAL")
    waiting_identity = read_json(page, "#identity")
    assert waiting_identity["execution_count"] == 0
    page.locator("#approve").click()
    page.wait_for_function(
        "() => document.querySelector('#statusText')?.textContent?.trim() === 'COMPLETED'"
    )
    approved_identity = read_json(page, "#identity")
    assert approved_identity["execution_count"] == 1

    return {
        "deterministic_request_fingerprint": first_fingerprint,
        "different_run_ids_same_input": True,
        "duplicate_execution_count": replay_identity["execution_count"],
        "blocked_execution_count": blocked_identity["execution_count"],
        "conflict_execution_count": conflict_identity["execution_count"],
        "approved_execution_count": approved_identity["execution_count"],
    }


def capture(page: Page, base_url: str, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#highRisk", "WAITING APPROVAL")
    waiting = output / "ai-agent-control-plane-desktop-waiting.png"
    page.screenshot(path=str(waiting), full_page=True)
    generated.append(waiting)

    page.locator("#approve").click()
    page.wait_for_function(
        "() => document.querySelector('#statusText')?.textContent?.trim() === 'COMPLETED'"
    )
    approved = output / "ai-agent-control-plane-desktop-approved.png"
    page.screenshot(path=str(approved), full_page=True)
    generated.append(approved)

    page.locator("#reset").click()
    click_and_wait(page, "#blockedRisk", "BLOCKED")
    blocked = output / "ai-agent-control-plane-desktop-blocked.png"
    page.screenshot(path=str(blocked), full_page=True)
    generated.append(blocked)

    page.locator("#reset").click()
    click_and_wait(page, "#lowRisk", "COMPLETED")
    click_and_wait(page, "#replaySame", "COMPLETED")
    replay = output / "ai-agent-control-plane-desktop-idempotency.png"
    page.screenshot(path=str(replay), full_page=True)
    generated.append(replay)

    return generated


def capture_mobile(browser: Any, base_url: str, output: Path) -> Path:
    context = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#highRisk", "WAITING APPROVAL")
    path = output / "ai-agent-control-plane-mobile-waiting.png"
    page.screenshot(path=str(path), full_page=True)
    context.close()
    return path


def create_gif(images: list[Path], output: Path) -> None:
    frames = [Image.open(path).convert("RGB") for path in images]
    width = max(frame.width for frame in frames)
    height = max(frame.height for frame in frames)
    normalized: list[Image.Image] = []
    for frame in frames:
        canvas = Image.new("RGB", (width, height), (8, 11, 8))
        canvas.paste(frame, (0, 0))
        normalized.append(canvas)
    normalized[0].save(
        output,
        save_all=True,
        append_images=normalized[1:],
        duration=[1500, 1500, 1800, 1800],
        loop=0,
        optimize=True,
    )
    for frame in frames:
        frame.close()


def dimensions(path: Path) -> dict[str, int | str]:
    with Image.open(path) as image:
        return {"file": path.name, "width": image.width, "height": image.height}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", default="docs/assets")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = context.new_page()
        verification = verify_demo(page, args.url)
        generated: list[Path] = []
        if not args.verify_only:
            generated = capture(page, args.url, output)
            generated.append(capture_mobile(browser, args.url, output))
            gif = output / "ai-agent-control-plane-proof.gif"
            create_gif(generated[:4], gif)
            generated.append(gif)
            manifest = {
                "generated_from": args.url,
                "browser": "chromium",
                "verification": verification,
                "assets": [dimensions(path) for path in generated],
            }
            (output / "visual-proof-manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
