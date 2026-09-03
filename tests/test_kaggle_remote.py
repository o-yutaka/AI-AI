from __future__ import annotations

import json
from pathlib import Path

import pytest

from security_lab.kaggle_remote import (
    KaggleRemoteJob,
    KaggleRemoteRunner,
    KaggleRunMode,
    stage_workspace,
    workspace_fingerprint,
)


def _workspace(tmp_path: Path, *, gpu: bool = False) -> Path:
    root = tmp_path / "workspace"
    root.mkdir(parents=True)
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('hello')\n"],
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
                "id": "owner/demo",
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


def test_staging_injects_marker_without_modifying_editable_notebook(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = (workspace / "notebook.ipynb").read_text(encoding="utf-8")
    fingerprint = workspace_fingerprint(workspace)
    staged = stage_workspace(workspace, tmp_path / "cache", fingerprint)

    after = (workspace / "notebook.ipynb").read_text(encoding="utf-8")
    staged_payload = json.loads((staged / "notebook.ipynb").read_text(encoding="utf-8"))

    assert before == after
    assert len(staged_payload["cells"]) == 2
    assert staged_payload["cells"][-1]["metadata"]["tags"] == [
        "security-lab-fingerprint"
    ]


def test_resource_modes_require_explicit_matching_metadata(tmp_path: Path) -> None:
    cpu_workspace = _workspace(tmp_path / "cpu")
    gpu_workspace = _workspace(tmp_path / "gpu", gpu=True)

    KaggleRemoteRunner._assert_resource_mode(cpu_workspace, KaggleRunMode.CPU)
    KaggleRemoteRunner._assert_resource_mode(gpu_workspace, KaggleRunMode.GPU)

    with pytest.raises(ValueError):
        KaggleRemoteRunner._assert_resource_mode(cpu_workspace, KaggleRunMode.GPU)
    with pytest.raises(ValueError):
        KaggleRemoteRunner._assert_resource_mode(gpu_workspace, KaggleRunMode.CPU)


def test_reuse_only_returns_matching_local_cache_without_kaggle_execution(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    fingerprint = workspace_fingerprint(workspace)
    cache = tmp_path / "cache"
    output = cache / "outputs" / fingerprint
    output.mkdir(parents=True)
    (output / "security-lab-result.json").write_text(
        json.dumps({"job_fingerprint": fingerprint}) + "\n",
        encoding="utf-8",
    )
    (output / "result.txt").write_text("cached\n", encoding="utf-8")

    runner = KaggleRemoteRunner()
    result = runner.run(
        KaggleRemoteJob(
            notebook_ref="owner/demo",
            output_dir=tmp_path / "download",
            cache_dir=cache,
            workspace_dir=workspace,
            mode=KaggleRunMode.REUSE_ONLY,
        )
    )

    assert result.source == "local-cache"
    assert result.executed is False
    assert result.verified_fingerprint is True
    assert result.output_dir == output
