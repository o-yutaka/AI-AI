from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class KaggleRunMode(StrEnum):
    REUSE_ONLY = "reuse-only"
    CPU = "cpu"
    GPU = "gpu"


@dataclass(frozen=True)
class KaggleRemoteJob:
    notebook_ref: str
    output_dir: Path
    cache_dir: Path
    workspace_dir: Path | None = None
    mode: KaggleRunMode = KaggleRunMode.REUSE_ONLY
    poll_seconds: float = 5.0
    timeout_seconds: float = 15 * 60


@dataclass(frozen=True)
class KaggleRemoteResult:
    notebook_ref: str
    job_fingerprint: str | None
    output_dir: Path
    output_sha256: str
    source: str
    executed: bool
    verified_fingerprint: bool


class KaggleRemoteRunner:
    """Output-first Kaggle notebook runner.

    REUSE_ONLY never executes a Kaggle notebook. It only returns a matching local
    cache entry or downloads the latest remote notebook output.

    CPU/GPU modes stage the current local notebook workspace, inject a result
    fingerprint marker into the staged copy, push that staged workspace, wait for
    completion, and then download output. The editable source workspace is never
    modified.
    """

    def run(self, job: KaggleRemoteJob) -> KaggleRemoteResult:
        fingerprint = (
            workspace_fingerprint(job.workspace_dir)
            if job.workspace_dir is not None
            else None
        )
        if fingerprint is not None:
            cached = self._cached_result(job, fingerprint)
            if cached is not None:
                return cached

        if job.mode is KaggleRunMode.REUSE_ONLY:
            return self._download_remote_output(job, fingerprint, executed=False)

        if job.workspace_dir is None:
            raise ValueError("workspace_dir is required for cpu/gpu execution")
        self._assert_resource_mode(job.workspace_dir, job.mode)
        staged = stage_workspace(job.workspace_dir, job.cache_dir, fingerprint or "unknown")
        self._run_cli(["kaggle", "kernels", "push", "-p", str(staged)])
        self._wait(job)
        return self._download_remote_output(job, fingerprint, executed=True)

    def _cached_result(
        self,
        job: KaggleRemoteJob,
        fingerprint: str,
    ) -> KaggleRemoteResult | None:
        cache_path = job.cache_dir / "outputs" / fingerprint
        marker = cache_path / "security-lab-result.json"
        if not marker.is_file():
            return None
        payload = json.loads(marker.read_text(encoding="utf-8"))
        if payload.get("job_fingerprint") != fingerprint:
            return None
        return KaggleRemoteResult(
            notebook_ref=job.notebook_ref,
            job_fingerprint=fingerprint,
            output_dir=cache_path,
            output_sha256=directory_sha256(cache_path),
            source="local-cache",
            executed=False,
            verified_fingerprint=True,
        )

    def _download_remote_output(
        self,
        job: KaggleRemoteJob,
        fingerprint: str | None,
        *,
        executed: bool,
    ) -> KaggleRemoteResult:
        job.output_dir.mkdir(parents=True, exist_ok=True)
        self._run_cli(
            [
                "kaggle",
                "kernels",
                "output",
                job.notebook_ref,
                "-p",
                str(job.output_dir),
                "--force",
            ]
        )
        marker = job.output_dir / "security-lab-result.json"
        verified = False
        if marker.is_file() and fingerprint is not None:
            payload = json.loads(marker.read_text(encoding="utf-8"))
            verified = payload.get("job_fingerprint") == fingerprint
        output_hash = directory_sha256(job.output_dir)

        if fingerprint is not None and verified:
            cache_path = job.cache_dir / "outputs" / fingerprint
            if cache_path.exists():
                shutil.rmtree(cache_path)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(job.output_dir, cache_path)

        return KaggleRemoteResult(
            notebook_ref=job.notebook_ref,
            job_fingerprint=fingerprint,
            output_dir=job.output_dir,
            output_sha256=output_hash,
            source="kaggle-output",
            executed=executed,
            verified_fingerprint=verified,
        )

    def _wait(self, job: KaggleRemoteJob) -> None:
        deadline = time.monotonic() + job.timeout_seconds
        while time.monotonic() < deadline:
            completed = self._run_cli(
                ["kaggle", "kernels", "status", job.notebook_ref],
                capture=True,
            ).lower()
            if "complete" in completed:
                return
            if "error" in completed or "cancel" in completed:
                raise RuntimeError(f"Kaggle notebook failed: {completed.strip()}")
            time.sleep(job.poll_seconds)
        raise TimeoutError(f"Kaggle notebook timed out: {job.notebook_ref}")

    @staticmethod
    def _assert_resource_mode(workspace_dir: Path, mode: KaggleRunMode) -> None:
        metadata = _load_metadata(workspace_dir)
        gpu = bool(metadata.get("enable_gpu", False))
        tpu = bool(metadata.get("enable_tpu", False))
        if mode is KaggleRunMode.CPU and (gpu or tpu):
            raise ValueError("cpu mode requires enable_gpu=false and enable_tpu=false")
        if mode is KaggleRunMode.GPU and (not gpu or tpu):
            raise ValueError("gpu mode requires enable_gpu=true and enable_tpu=false")

    @staticmethod
    def _run_cli(command: list[str], *, capture: bool = False) -> str:
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture,
        )
        return completed.stdout if capture else ""


def workspace_fingerprint(workspace_dir: Path) -> str:
    root = workspace_dir.resolve()
    if not root.is_dir():
        raise ValueError(f"workspace not found: {root}")
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if any(part in {".git", ".kaggle-lab", "__pycache__"} for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def directory_sha256(directory: Path) -> str:
    root = directory.resolve()
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def stage_workspace(workspace_dir: Path, cache_dir: Path, fingerprint: str) -> Path:
    metadata = _load_metadata(workspace_dir)
    code_file = metadata.get("code_file")
    if not isinstance(code_file, str) or not code_file:
        raise ValueError("kernel-metadata.json must define code_file")

    destination = cache_dir / "staged" / fingerprint
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(workspace_dir, destination)

    code_path = destination / code_file
    if code_path.suffix == ".ipynb":
        _inject_notebook_marker(code_path, fingerprint)
    elif code_path.suffix == ".py":
        _inject_script_marker(code_path, fingerprint)
    else:
        raise ValueError(f"unsupported Kaggle code_file: {code_file}")
    return destination


def _load_metadata(workspace_dir: Path) -> dict[str, Any]:
    path = workspace_dir / "kernel-metadata.json"
    if not path.is_file():
        raise ValueError(f"kernel-metadata.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _inject_notebook_marker(path: Path, fingerprint: str) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    notebook.setdefault("cells", []).append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {"tags": ["security-lab-fingerprint"]},
            "outputs": [],
            "source": _marker_source(fingerprint),
        }
    )
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _inject_script_marker(path: Path, fingerprint: str) -> None:
    source = path.read_text(encoding="utf-8")
    path.write_text(source + "\n\n" + "".join(_marker_source(fingerprint)), encoding="utf-8")


def _marker_source(fingerprint: str) -> list[str]:
    payload = json.dumps({"job_fingerprint": fingerprint}, sort_keys=True)
    return [
        "from pathlib import Path\n",
        f"Path('security-lab-result.json').write_text({payload!r} + '\\n', encoding='utf-8')\n",
    ]
