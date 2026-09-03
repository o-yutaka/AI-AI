from __future__ import annotations

import json
import subprocess
from pathlib import Path

from security_lab.kaggle_remote import KaggleRemoteRunner, stage_scratch_script


def test_stage_scratch_script_is_private_offline_and_competition_bound(tmp_path: Path) -> None:
    root = stage_scratch_script(
        tmp_path,
        kernel_ref="owner/black-scratch",
        title="BLACK Scratch",
        source="print('ok')",
        competition_slug="ai-agent-security-multi-step-tool-attacks",
    )
    metadata = json.loads((root / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert metadata["is_private"] is True
    assert metadata["enable_internet"] is False
    assert metadata["enable_gpu"] is True
    assert metadata["machine_shape"] == "NvidiaTeslaT4"
    assert metadata["competition_sources"] == ["ai-agent-security-multi-step-tool-attacks"]


def test_status_parser_normalizes_cli_text(monkeypatch) -> None:
    monkeypatch.setattr("security_lab.kaggle_remote.shutil.which", lambda _: "/usr/bin/kaggle")

    def run(command):
        return subprocess.CompletedProcess(command, 0, "status: complete\n", "")

    assert KaggleRemoteRunner(run).status("owner/kernel") == "COMPLETE"
