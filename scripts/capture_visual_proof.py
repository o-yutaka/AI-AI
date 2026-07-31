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
        arg=status,
    )


def wait_for_status(page: Page, status: str) -> None:
    page.wait_for_function(
        "expected => document.querySelector('#statusText')?.textContent?.trim() === expected",
        arg=status,
    )


def replay_same_and_wait(page: Page) -> None:
    page.locator("#replaySame").click()
    page.wait_for_function(
        "() => document.querySelector('#metricReplay')?.textContent?.trim() === 'REUSED'"
    )


def replay_conflict_and_wait(page: Page) -> None:
    page.locator("#replayConflict").click()
    page.wait_for_function(
        "() => document.querySelector('#result')?.textContent?.includes('IdempotencyConflictError')"
    )


def verify_demo(page: Page, base_url: str) -> dict[str, Any]:
    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#lowRisk", "completed")
    first_identity = read_json(page, "#identity")
    first_run_id = first_identity["run_id"]
    first_fingerprint = first_identity["request_fingerprint"]
    assert first_identity["execution_count"] == 1
    assert first_identity["canonical_input_excludes_run_id"] is True

    page.locator("#reset").click()
    click_and_wait(page, "#lowRisk", "completed")
    second_identity = read_json(page, "#identity")
    assert second_identity["run_id"] != first_run_id
    assert second_identity["request_fingerprint"] == first_fingerprint

    replay_same_and_wait(page)
    replay_identity = read_json(page, "#identity")
    assert replay_identity["run_id"] == second_identity["run_id"]
    assert replay_identity["execution_count"] == 1
    assert replay_identity["idempotency_replayed"] is True

    click_and_wait(page, "#blockedRisk", "blocked")
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

    replay_conflict_and_wait(page)
    conflict = read_json(page, "#result")
    assert conflict["error_type"] == "IdempotencyConflictError"
    conflict_identity = read_json(page, "#identity")
    assert conflict_identity["execution_count"] == 0

    click_and_wait(page, "#highRisk", "waiting approval")
    waiting_identity = read_json(page, "#identity")
    assert waiting_identity["execution_count"] == 0
    page.locator("#approve").click()
    wait_for_status(page, "completed")
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


def screenshot(page: Page, output: Path, name: str) -> Path:
    path = output / name
    page.screenshot(path=str(path), full_page=True, type="jpeg", quality=82)
    return path


def capture(page: Page, base_url: str, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#highRisk", "waiting approval")
    generated.append(
        screenshot(page, output, "ai-agent-control-plane-desktop-waiting.jpg")
    )

    page.locator("#approve").click()
    wait_for_status(page, "completed")
    generated.append(
        screenshot(page, output, "ai-agent-control-plane-desktop-approved.jpg")
    )

    page.locator("#reset").click()
    click_and_wait(page, "#blockedRisk", "blocked")
    generated.append(
        screenshot(page, output, "ai-agent-control-plane-desktop-blocked.jpg")
    )

    page.locator("#reset").click()
    click_and_wait(page, "#lowRisk", "completed")
    replay_same_and_wait(page)
    generated.append(
        screenshot(page, output, "ai-agent-control-plane-desktop-idempotency.jpg")
    )

    return generated


def capture_mobile(browser: Any, base_url: str, output: Path) -> Path:
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=1,
    )
    page = context.new_page()
    page.goto(base_url, wait_until="networkidle")
    click_and_wait(page, "#highRisk", "waiting approval")
    path = screenshot(page, output, "ai-agent-control-plane-mobile-waiting.jpg")
    context.close()
    return path


def create_compact_gif(images: list[Path], output: Path) -> None:
    frames: list[Image.Image] = []
    for path in images:
        with Image.open(path) as source:
            frame = source.convert("RGB")
            frame = frame.crop((0, 0, frame.width, min(1350, frame.height)))
            width = 640
            height = round(frame.height * width / frame.width)
            frame = frame.resize((width, height), Image.Resampling.LANCZOS)
            frame = frame.quantize(
                colors=48,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.NONE,
            )
            frames.append(frame)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=[1400, 1400, 1700, 1700],
        loop=0,
        optimize=True,
        disposal=2,
    )


def dimensions(path: Path) -> dict[str, int | str]:
    with Image.open(path) as image:
        return {
            "file": path.name,
            "width": image.width,
            "height": image.height,
            "bytes": path.stat().st_size,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", default="docs/assets/proof")
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
            create_compact_gif(generated[:4], gif)
            generated.append(gif)
            manifest = {
                "generated_from": "docs/live-demo.html",
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
