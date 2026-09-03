from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class RuntimeTelemetry:
    run_id: str
    model_id: str
    compiler_id: str
    duration_ms: float
    input_units: int | None
    output_units: int | None
    completed: bool
    outcome: str
    runtime_version: str
    metadata: dict[str, Any]


def measure_runtime(
    *,
    run_id: str,
    model_id: str,
    compiler_id: str,
    runtime_version: str,
    execute: Callable[[], Any],
    metadata: dict[str, Any] | None = None,
) -> tuple[Any, RuntimeTelemetry]:
    started = perf_counter()
    try:
        result = execute()
        telemetry = RuntimeTelemetry(
            run_id=run_id,
            model_id=model_id,
            compiler_id=compiler_id,
            duration_ms=(perf_counter() - started) * 1000,
            input_units=None,
            output_units=None,
            completed=True,
            outcome="OK",
            runtime_version=runtime_version,
            metadata=dict(metadata or {}),
        )
        return result, telemetry
    except Exception as exc:
        telemetry = RuntimeTelemetry(
            run_id=run_id,
            model_id=model_id,
            compiler_id=compiler_id,
            duration_ms=(perf_counter() - started) * 1000,
            input_units=None,
            output_units=None,
            completed=False,
            outcome=type(exc).__name__,
            runtime_version=runtime_version,
            metadata=dict(metadata or {}),
        )
        exc.security_lab_telemetry = asdict(telemetry)
        raise
