from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .timing_signal import (
    TimingCalibration,
    TimingOutcome,
    TimingSample,
    fit_timing_calibration,
    infer_timing_survival,
)


def timing_calibrations_from_mapping(
    raw: Mapping[str, Any] | None,
) -> dict[str, TimingCalibration]:
    if raw is None:
        return {}
    calibrations: dict[str, TimingCalibration] = {}
    for calibration_id, calibration_raw in raw.items():
        if not calibration_id:
            raise ValueError("timing calibration id must be non-empty")
        item = _mapping(calibration_raw)
        samples = tuple(_sample(_mapping(sample)) for sample in _sequence(item["samples"]))
        calibrations[str(calibration_id)] = fit_timing_calibration(
            samples,
            minimum_samples_per_class=int(item.get("minimum_samples_per_class", 3)),
            minimum_separation_s=float(item.get("minimum_separation_s", 0.0)),
        )
    return calibrations


def resolve_private_survival_probability(
    raw: Mapping[str, Any],
    calibrations: Mapping[str, TimingCalibration],
) -> float:
    explicit = raw.get("private_survival_probability")
    timing_raw = raw.get("timing_signal")
    if explicit is not None and timing_raw is not None:
        raise ValueError(
            "finding must use either private_survival_probability or timing_signal, not both"
        )
    if timing_raw is None:
        return float(explicit if explicit is not None else 1.0)

    timing = _mapping(timing_raw)
    calibration_id = str(timing["calibration_id"])
    try:
        calibration = calibrations[calibration_id]
    except KeyError as exc:
        raise ValueError(f"unknown timing calibration: {calibration_id}") from exc
    elapsed = tuple(float(value) for value in _sequence(timing["elapsed_seconds"]))
    report = infer_timing_survival(
        calibration,
        elapsed,
        environment_key=str(timing["environment_key"]),
    )
    return report.conservative_success_probability


def _sample(raw: Mapping[str, Any]) -> TimingSample:
    return TimingSample(
        sample_id=str(raw["sample_id"]),
        outcome=TimingOutcome(str(raw["outcome"])),
        elapsed_seconds=float(raw["elapsed_seconds"]),
        environment_key=str(raw["environment_key"]),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected JSON object")
    return value


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("expected JSON array")
    return value
