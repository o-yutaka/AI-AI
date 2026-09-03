from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Callable


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
        completed = True
        outcome = "OK"
        return result, RuntimeTelemetry(
            run_id, model_id, compiler_id, (perf_counter() - started) * 1000,
            None, None, completed, outcome, runtime_version, dict(metadata or {}),
        )
    except Exception as exc:
        telemetry = RuntimeTelemetry(
            run_id, model_id, compiler_id, (perf_counter() - started) * 1000,
            None, None, False, type(exc).__name__, runtime_version, dict(metadata or {}),
        )
        setattr(exc, "security_lab_telemetry", asdict(telemetry))
        raise
