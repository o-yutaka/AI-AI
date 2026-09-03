# ruff: noqa: I001
from __future__ import annotations

import collections.abc
import dataclasses
import hashlib
import json
import pathlib
import shutil
import subprocess
import time
from enum import StrEnum


CommandRunner = collections.abc.Callable[
    [collections.abc.Sequence[str]],
    subprocess.CompletedProcess[str],
]


class KaggleRunMode(StrEnum):
    REUSE_ONLY = "reuse-only"
    CPU = "cpu"
    GPU = "gpu"


@dataclasses.dataclass(frozen=True)
class KaggleRemoteSpec:
    kernel_ref: str
    source_dir: pathlib.Path
    output_dir: pathlib.Path
    cache_dir: pathlib.Path = pathlib.Path(".kaggle-lab")
    mode: KaggleRunMode = KaggleRunMode.REUSE_ONLY
    poll_seconds: float = 15.0
    timeout_seconds: float = 54_000.0


@dataclasses.dataclass(frozen=True)
class KaggleRemoteResult:
    kernel_ref: str
    status: str
    output_dir: pathlib.Path
    output_files: tuple[str, ...]
    job_fingerprint: str
    output_sha256: str
    source: str
    executed: bool
    verified_fingerprint: bool


def stage_scratch_script(
    destination: str | pathlib.Path,
    *,
    kernel_ref: str,
    title: str,
    source: str,
    competition_slug: str | None = None,
    enable_gpu: bool = True,
    machine_shape: str = "NvidiaTeslaT4",
) -> pathlib.Path:
    root = pathlib.Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    script = root / "black_kaggle_task.py"
    metadata = root / "kernel-metadata.json"
    script.write_text(source.rstrip() + "\n", encoding="utf-8")
    metadata.write_text(
        json.dumps(
            {
                "id": kernel_ref,
                "title": title,
                "code_file": script.name,
                "language": "python",
                "kernel_type": "script",
                "is_private": True,
                "enable_gpu": enable_gpu,
                "enable_internet": False,
                "machine_shape": machine_shape if enable_gpu else "",
                "dataset_sources": [],
                "competition_sources": [competition_slug] if competition_slug else [],
                "kernel_sources": [],
                "model_sources": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return root


class KaggleRemoteRunner:
    def __init__(self, run_command: CommandRunner | None = None) -> None:
        self._run = run_command or _run_command

    def run(self, spec: KaggleRemoteSpec) -> KaggleRemoteResult:
        """Return matching output first; execute only for explicit cpu/gpu modes."""
        self._require_cli()
        fingerprint = workspace_fingerprint(spec.source_dir)
        cached = self._cached_result(spec, fingerprint)
        if cached is not None:
            return cached

        if spec.mode is KaggleRunMode.REUSE_ONLY:
            files = self.output(spec.kernel_ref, spec.output_dir)
            verified = marker_matches(spec.output_dir, fingerprint)
            output_hash = directory_sha256(spec.output_dir)
            if verified:
                self._cache_output(spec, fingerprint)
            return KaggleRemoteResult(
                kernel_ref=spec.kernel_ref,
                status="REUSED_REMOTE_OUTPUT",
                output_dir=spec.output_dir,
                output_files=files,
                job_fingerprint=fingerprint,
                output_sha256=output_hash,
                source="kaggle-output",
                executed=False,
                verified_fingerprint=verified,
            )

        self._assert_resource_mode(spec.source_dir, spec.mode)
        staged = stage_workspace(spec.source_dir, spec.cache_dir, fingerprint)
        self._run(["kaggle", "kernels", "update", "-p", str(staged)])
        status = self._wait(spec)
        files = self.output(spec.kernel_ref, spec.output_dir)
        verified = marker_matches(spec.output_dir, fingerprint)
        if not verified:
            raise RuntimeError(
                "Kaggle output completed but fingerprint marker did not match staged source"
            )
        output_hash = directory_sha256(spec.output_dir)
        self._cache_output(spec, fingerprint)
        return KaggleRemoteResult(
            kernel_ref=spec.kernel_ref,
            status=status,
            output_dir=spec.output_dir,
            output_files=files,
            job_fingerprint=fingerprint,
            output_sha256=output_hash,
            source="kaggle-execution",
            executed=True,
            verified_fingerprint=True,
        )

    def status(self, kernel_ref: str) -> str:
        self._require_cli()
        completed = self._run(["kaggle", "kernels", "status", kernel_ref])
        text = f"{completed.stdout}\n{completed.stderr}".lower()
        if "complete" in text:
            return "COMPLETE"
        if "error" in text or "failed" in text:
            return "ERROR"
        if "running" in text:
            return "RUNNING"
        if "queued" in text or "pending" in text:
            return "QUEUED"
        return "UNKNOWN"

    def output(
        self,
        kernel_ref: str,
        destination: str | pathlib.Path,
    ) -> tuple[str, ...]:
        self._require_cli()
        output_dir = pathlib.Path(destination)
        output_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "kaggle",
                "kernels",
                "output",
                kernel_ref,
                "-p",
                str(output_dir),
                "-o",
                "-q",
            ]
        )
        files = (
            str(path.relative_to(output_dir))
            for path in output_dir.rglob("*")
            if path.is_file()
        )
        return tuple(sorted(files))

    def submit(
        self,
        *,
        competition_slug: str,
        kernel_ref: str,
        output_file: str,
        message: str,
        version: int | None = None,
    ) -> str:
        """Explicitly submit one completed kernel output. Never called by run()."""
        self._require_cli()
        command = [
            "kaggle",
            "competitions",
            "submit",
            competition_slug,
            "-k",
            kernel_ref,
            "-f",
            output_file,
            "-m",
            message,
        ]
        if version is not None:
            command.extend(["-v", str(version)])
        completed = self._run(command)
        return completed.stdout.strip()

    def _wait(self, spec: KaggleRemoteSpec) -> str:
        deadline = time.monotonic() + spec.timeout_seconds
        while time.monotonic() < deadline:
            status = self.status(spec.kernel_ref)
            if status == "COMPLETE":
                return status
            if status == "ERROR":
                raise RuntimeError(f"Kaggle kernel failed: {spec.kernel_ref}")
            time.sleep(spec.poll_seconds)
        raise TimeoutError(f"Kaggle kernel timed out: {spec.kernel_ref}")

    def _cached_result(
        self,
        spec: KaggleRemoteSpec,
        fingerprint: str,
    ) -> KaggleRemoteResult | None:
        cache = spec.cache_dir / "outputs" / fingerprint
        if not marker_matches(cache, fingerprint):
            return None
        files = tuple(
            sorted(
                str(path.relative_to(cache))
                for path in cache.rglob("*")
                if path.is_file()
            )
        )
        return KaggleRemoteResult(
            kernel_ref=spec.kernel_ref,
            status="REUSED_LOCAL_CACHE",
            output_dir=cache,
            output_files=files,
            job_fingerprint=fingerprint,
            output_sha256=directory_sha256(cache),
            source="local-cache",
            executed=False,
            verified_fingerprint=True,
        )

    @staticmethod
    def _cache_output(spec: KaggleRemoteSpec, fingerprint: str) -> None:
        cache = spec.cache_dir / "outputs" / fingerprint
        if cache.exists():
            shutil.rmtree(cache)
        cache.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(spec.output_dir, cache)

    @staticmethod
    def _assert_resource_mode(source_dir: pathlib.Path, mode: KaggleRunMode) -> None:
        metadata = load_kernel_metadata(source_dir)
        gpu = bool(metadata.get("enable_gpu", False))
        tpu = bool(metadata.get("enable_tpu", False))
        if mode is KaggleRunMode.CPU and (gpu or tpu):
            raise ValueError("cpu mode requires enable_gpu=false and enable_tpu=false")
        if mode is KaggleRunMode.GPU and (not gpu or tpu):
            raise ValueError("gpu mode requires enable_gpu=true and enable_tpu=false")

    @staticmethod
    def _require_cli() -> None:
        if shutil.which("kaggle") is None:
            raise RuntimeError("Kaggle CLI not found; install it and run `kaggle auth login`")


def workspace_fingerprint(source_dir: str | pathlib.Path) -> str:
    root = pathlib.Path(source_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"Kaggle source directory not found: {root}")
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


def directory_sha256(directory: str | pathlib.Path) -> str:
    root = pathlib.Path(directory).resolve()
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def load_kernel_metadata(source_dir: str | pathlib.Path) -> dict[str, object]:
    path = pathlib.Path(source_dir) / "kernel-metadata.json"
    if not path.is_file():
        raise ValueError(f"kernel-metadata.json not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("kernel-metadata.json must contain a JSON object")
    return payload


def stage_workspace(
    source_dir: str | pathlib.Path,
    cache_dir: str | pathlib.Path,
    fingerprint: str,
) -> pathlib.Path:
    source = pathlib.Path(source_dir)
    metadata = load_kernel_metadata(source)
    code_file = metadata.get("code_file")
    if not isinstance(code_file, str) or not code_file:
        raise ValueError("kernel-metadata.json must define code_file")

    destination = pathlib.Path(cache_dir) / "staged" / fingerprint
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)

    code_path = destination / code_file
    if code_path.suffix == ".ipynb":
        _inject_notebook_marker(code_path, fingerprint)
    elif code_path.suffix == ".py":
        _inject_script_marker(code_path, fingerprint)
    else:
        raise ValueError(f"unsupported Kaggle code_file: {code_file}")
    return destination


def marker_matches(directory: str | pathlib.Path, fingerprint: str) -> bool:
    marker = pathlib.Path(directory) / "security-lab-result.json"
    if not marker.is_file():
        return False
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return isinstance(payload, dict) and payload.get("job_fingerprint") == fingerprint


def _inject_notebook_marker(path: pathlib.Path, fingerprint: str) -> None:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    cells = notebook.setdefault("cells", [])
    if not isinstance(cells, list):
        raise ValueError("notebook cells must be a list")
    cells.append(
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {"tags": ["security-lab-fingerprint"]},
            "outputs": [],
            "source": _marker_source(fingerprint),
        }
    )
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _inject_script_marker(path: pathlib.Path, fingerprint: str) -> None:
    source = path.read_text(encoding="utf-8")
    path.write_text(source.rstrip() + "\n\n" + "".join(_marker_source(fingerprint)), encoding="utf-8")


def _marker_source(fingerprint: str) -> list[str]:
    payload = json.dumps({"job_fingerprint": fingerprint}, sort_keys=True)
    return [
        "from pathlib import Path\n",
        f"Path('security-lab-result.json').write_text({payload!r} + '\\n', encoding='utf-8')\n",
    ]


def _run_command(
    command: collections.abc.Sequence[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(command), check=True, capture_output=True, text=True)
