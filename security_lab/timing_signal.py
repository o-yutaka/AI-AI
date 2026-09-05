from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import exp
from statistics import median


class TimingOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class TimingSample:
    sample_id: str
    outcome: TimingOutcome
    elapsed_seconds: float
    environment_key: str

    def __post_init__(self) -> None:
        if not self.sample_id:
            raise ValueError("sample_id must be non-empty")
        if not self.environment_key:
            raise ValueError("environment_key must be non-empty")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be non-negative")


@dataclass(frozen=True)
class TimingCalibration:
    environment_key: str
    success_median_s: float
    blocked_median_s: float
    threshold_s: float
    success_is_faster: bool
    separation_s: float
    scale_s: float
    success_samples: int
    blocked_samples: int


@dataclass(frozen=True)
class TimingInferenceReport:
    sample_count: int
    probabilities: tuple[float, ...]
    mean_success_probability: float
    median_success_probability: float
    conservative_success_probability: float


def fit_timing_calibration(
    samples: tuple[TimingSample, ...],
    *,
    minimum_samples_per_class: int = 3,
    minimum_separation_s: float = 0.0,
) -> TimingCalibration:
    """Calibrate a latency discriminator from labeled benchmark replay evidence.

    This is intentionally environment-bound. Mixing model/runtime/compiler identities
    would turn timing drift into a false policy signal, so calibration rejects mixed
    environment keys.
    """

    if minimum_samples_per_class < 1:
        raise ValueError("minimum_samples_per_class must be positive")
    if minimum_separation_s < 0:
        raise ValueError("minimum_separation_s must be non-negative")
    if not samples:
        raise ValueError("timing calibration requires samples")

    environment_keys = {sample.environment_key for sample in samples}
    if len(environment_keys) != 1:
        raise ValueError("timing calibration cannot mix environment identities")
    environment_key = next(iter(environment_keys))

    success = [
        sample.elapsed_seconds
        for sample in samples
        if sample.outcome is TimingOutcome.SUCCESS
    ]
    blocked = [
        sample.elapsed_seconds
        for sample in samples
        if sample.outcome is TimingOutcome.BLOCKED
    ]
    if len(success) < minimum_samples_per_class or len(blocked) < minimum_samples_per_class:
        raise ValueError("timing calibration has insufficient samples per outcome")

    success_median = median(success)
    blocked_median = median(blocked)
    separation = abs(blocked_median - success_median)
    if separation <= minimum_separation_s:
        raise ValueError(
            "timing calibration separation is too small for a reliable discriminator"
        )

    pooled_deviation = [
        abs(value - success_median) for value in success
    ] + [abs(value - blocked_median) for value in blocked]
    robust_noise = median(pooled_deviation) if pooled_deviation else 0.0
    scale = max(robust_noise, separation / 6.0, 1e-6)

    return TimingCalibration(
        environment_key=environment_key,
        success_median_s=success_median,
        blocked_median_s=blocked_median,
        threshold_s=(success_median + blocked_median) / 2.0,
        success_is_faster=success_median < blocked_median,
        separation_s=separation,
        scale_s=scale,
        success_samples=len(success),
        blocked_samples=len(blocked),
    )


def timing_success_probability(
    calibration: TimingCalibration,
    *,
    elapsed_seconds: float,
    environment_key: str,
) -> float:
    if elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be non-negative")
    if environment_key != calibration.environment_key:
        raise ValueError("timing inference environment does not match calibration")

    direction = -1.0 if calibration.success_is_faster else 1.0
    signed_distance = direction * (elapsed_seconds - calibration.threshold_s)
    z = max(-60.0, min(60.0, signed_distance / calibration.scale_s))
    return 1.0 / (1.0 + exp(-z))


def infer_timing_survival(
    calibration: TimingCalibration,
    elapsed_seconds: tuple[float, ...],
    *,
    environment_key: str,
) -> TimingInferenceReport:
    if not elapsed_seconds:
        raise ValueError("timing inference requires at least one observation")
    probabilities = tuple(
        timing_success_probability(
            calibration,
            elapsed_seconds=value,
            environment_key=environment_key,
        )
        for value in elapsed_seconds
    )
    ordered = sorted(probabilities)
    conservative_index = max(0, (len(ordered) - 1) // 4)
    return TimingInferenceReport(
        sample_count=len(probabilities),
        probabilities=probabilities,
        mean_success_probability=sum(probabilities) / len(probabilities),
        median_success_probability=median(probabilities),
        conservative_success_probability=ordered[conservative_index],
    )
