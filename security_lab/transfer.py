from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class TransferPair:
    proxy_score: float
    target_score: float


@dataclass(frozen=True)
class TransferEstimate:
    slope: float
    intercept: float
    residual_mae: float
    sample_count: int

    def predict(self, proxy_score: float) -> float:
        return self.intercept + self.slope * proxy_score


def fit_linear_transfer(pairs: list[TransferPair]) -> TransferEstimate:
    if len(pairs) < 2:
        raise ValueError(
            "transfer calibration requires at least two proxy/target pairs"
        )
    xs = [item.proxy_score for item in pairs]
    ys = [item.target_score for item in pairs]
    x_bar = mean(xs)
    y_bar = mean(ys)
    variance = sum((x - x_bar) ** 2 for x in xs)
    covariance = sum(
        (x - x_bar) * (y - y_bar)
        for x, y in zip(xs, ys, strict=True)
    )
    slope = 0.0 if variance == 0 else covariance / variance
    intercept = y_bar - slope * x_bar
    residuals = [
        abs((intercept + slope * x) - y)
        for x, y in zip(xs, ys, strict=True)
    ]
    return TransferEstimate(
        slope=slope,
        intercept=intercept,
        residual_mae=mean(residuals),
        sample_count=len(pairs),
    )
