from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from security_lab.kaggle_remote import (
    KaggleRemoteRunner,
    KaggleRemoteSpec,
    KaggleRunMode,
    stage_scratch_script,
    stage_workspace,
    workspace_fingerprint,
)


def test_stage_scratch_script_is_private_offline_and_competition_bound(tmp_path: Path) -> None:
    root = stage_scratch_script(
        tmp_path,
        kernel_ref="owner/black-scratch",
        title="BLACK Scratch",
        source="print('ok')",
        competition_slug="ai-agent-security-multi-step-tool-attacks",
        enable_gpu=True,
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


def _notebook_workspace(tmp_path: Path, *, gpu: bool = False) -> Path:
    root = tmp_path / "workspace"
    root.mkdir(parents=True)
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('research')\n"],
                "metadata": {},
                "outputs": [],
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (root / "notebook.ipynb").write_text(json.dumps(notebook), encoding="utf-8")
    (root / "kernel-metadata.json").write_text(
        json.dumps(
            {
                "id": "owner/kernel",
                "title": "Kernel",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": gpu,
                "enable_tpu": False,
                "enable_internet": False,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_reuse_only_downloads_output_without_executing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("security_lab.kaggle_remote.shutil.which", lambda _: "/usr/bin/kaggle")
    workspace = _notebook_workspace(tmp_path)
    fingerprint = workspace_fingerprint(workspace)
    commands: list[list[str]] = []

    def run(command):
        current = list(command)
        commands.append(current)
        if current[:3] == ["kaggle", "kernels", "output"]:
            destination = Path(current[current.index("-p") + 1])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "security-lab-result.json").write_text(
                json.dumps({"job_fingerprint": fingerprint}) + "\n",
                encoding="utf-8",
            )
            (destination / "score.json").write_text("{}\n", encoding="utf-8")
        return subprocess.CompletedProcess(current, 0, "", "")

    result = KaggleRemoteRunner(run).run(
        KaggleRemoteSpec(
            kernel_ref="owner/kernel",
            source_dir=workspace,
            output_dir=tmp_path / "output",
            cache_dir=tmp_path / "cache",
        )
    )

    assert result.executed is False
    assert result.verified_fingerprint is True
    assert result.source == "kaggle-output"
    assert all(current[:3] != ["kaggle", "kernels", "update"] for current in commands)


def test_matching_local_cache_avoids_even_remote_output(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("security_lab.kaggle_remote.shutil.which", lambda _: "/usr/bin/kaggle")
    workspace = _notebook_workspace(tmp_path)
    fingerprint = workspace_fingerprint(workspace)
    cached = tmp_path / "cache" / "outputs" / fingerprint
    cached.mkdir(parents=True)
    (cached / "security-lab-result.json").write_text(
        json.dumps({"job_fingerprint": fingerprint}) + "\n",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def run(command):
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0, "", "")

    result = KaggleRemoteRunner(run).run(
        KaggleRemoteSpec(
            kernel_ref="owner/kernel",
            source_dir=workspace,
            output_dir=tmp_path / "output",
            cache_dir=tmp_path / "cache",
        )
    )

    assert result.source == "local-cache"
    assert result.executed is False
    assert calls == []


def test_staged_execution_does_not_modify_editable_notebook(tmp_path: Path) -> None:
    workspace = _notebook_workspace(tmp_path, gpu=True)
    original = (workspace / "notebook.ipynb").read_text(encoding="utf-8")
    fingerprint = workspace_fingerprint(workspace)
    staged = stage_workspace(workspace, tmp_path / "cache", fingerprint)

    assert (workspace / "notebook.ipynb").read_text(encoding="utf-8") == original
    staged_notebook = json.loads((staged / "notebook.ipynb").read_text(encoding="utf-8"))
    assert staged_notebook["cells"][-1]["metadata"]["tags"] == [
        "security-lab-fingerprint"
    ]


def test_cpu_gpu_execution_requires_matching_metadata(tmp_path: Path) -> None:
    cpu = _notebook_workspace(tmp_path / "cpu", gpu=False)
    gpu = _notebook_workspace(tmp_path / "gpu", gpu=True)

    KaggleRemoteRunner._assert_resource_mode(cpu, KaggleRunMode.CPU)
    KaggleRemoteRunner._assert_resource_mode(gpu, KaggleRunMode.GPU)
    with pytest.raises(ValueError):
        KaggleRemoteRunner._assert_resource_mode(cpu, KaggleRunMode.GPU)
    with pytest.raises(ValueError):
        KaggleRemoteRunner._assert_resource_mode(gpu, KaggleRunMode.CPU)
