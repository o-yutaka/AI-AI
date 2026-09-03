from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class KaggleRemoteSpec:
    kernel_ref: str
    source_dir: Path
    output_dir: Path
    poll_seconds: float = 15.0
    timeout_seconds: float = 54_000.0


@dataclass(frozen=True)
class KaggleRemoteResult:
    kernel_ref: str
    status: str
    output_dir: Path
    output_files: tuple[str, ...]


def stage_scratch_script(
    destination: str | Path,
    *,
    kernel_ref: str,
    title: str,
    source: str,
    competition_slug: str | None = None,
    enable_gpu: bool = True,
    machine_shape: str = "NvidiaTeslaT4",
) -> Path:
    """Create a minimal private Kaggle script kernel for one remote experiment.

    This deliberately stages only the supplied source plus kernel metadata. It
    does not copy BLACK state, secrets, or local runtime data into the kernel.
    """
    root = Path(destination)
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
        self._require_cli()
        self._run(["kaggle", "kernels", "update", "-p", str(spec.source_dir)])
        deadline = time.monotonic() + spec.timeout_seconds
        status = "UNKNOWN"
        while time.monotonic() < deadline:
            status = self.status(spec.kernel_ref)
            if status == "COMPLETE":
                break
            if status == "ERROR":
                raise RuntimeError(f"Kaggle kernel failed: {spec.kernel_ref}")
            time.sleep(spec.poll_seconds)
        else:
            raise TimeoutError(f"Kaggle kernel timed out: {spec.kernel_ref}")

        spec.output_dir.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "kaggle",
                "kernels",
                "output",
                spec.kernel_ref,
                "-p",
                str(spec.output_dir),
                "-o",
                "-q",
            ]
        )
        files = tuple(
            sorted(
                str(path.relative_to(spec.output_dir))
                for path in spec.output_dir.rglob("*")
                if path.is_file()
            )
        )
        return KaggleRemoteResult(spec.kernel_ref, status, spec.output_dir, files)

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

    def output(self, kernel_ref: str, destination: str | Path) -> tuple[str, ...]:
        self._require_cli()
        output_dir = Path(destination)
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
        return tuple(
            sorted(
                str(path.relative_to(output_dir))
                for path in output_dir.rglob("*")
                if path.is_file()
            )
        )

    @staticmethod
    def _require_cli() -> None:
        if shutil.which("kaggle") is None:
            raise RuntimeError("Kaggle CLI not found; install it and run `kaggle auth login`")


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        capture_output=True,
        text=True,
    )
