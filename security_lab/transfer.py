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


@dataclass(frozen=True)
class RidgeTransferEstimate:
    slope: float
    intercept: float
    alpha: float
    residual_mae: float
    residual_max: float
    sample_count: int

    def predict(self, proxy_score: float) -> float:
        return self.intercept + self.slope * proxy_score

    def conservative_lower_bound(
        self,
        proxy_score: float,
        *,
        residual_multiplier: float = 1.0,
    ) -> float:
        if residual_multiplier < 0:
            raise ValueError("residual_multiplier must be non-negative")
        return self.predict(proxy_score) - residual_multiplier * self.residual_max


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


def fit_ridge_transfer(
    pairs: list[TransferPair],
    *,
    alpha: float = 1.0,
) -> RidgeTransferEstimate:
    """Fit a dependency-free one-feature ridge proxy→target calibration.

    Centering keeps the intercept unregularized while the slope is shrunk by
    ``alpha``. This is intentionally small and deterministic so the same
    calibration can be reproduced in local and competition runtimes.
    """

    if len(pairs) < 2:
        raise ValueError(
            "ridge transfer calibration requires at least two proxy/target pairs"
        )
    if alpha < 0:
        raise ValueError("alpha must be non-negative")

    xs = [item.proxy_score for item in pairs]
    ys = [item.target_score for item in pairs]
    x_bar = mean(xs)
    y_bar = mean(ys)
    variance = sum((x - x_bar) ** 2 for x in xs)
    covariance = sum(
        (x - x_bar) * (y - y_bar)
        for x, y in zip(xs, ys, strict=True)
    )
    denominator = variance + alpha
    slope = 0.0 if denominator == 0 else covariance / denominator
    intercept = y_bar - slope * x_bar
    residuals = [
        abs((intercept + slope * x) - y)
        for x, y in zip(xs, ys, strict=True)
    ]
    return RidgeTransferEstimate(
        slope=slope,
        intercept=intercept,
        alpha=alpha,
        residual_mae=mean(residuals),
        residual_max=max(residuals),
        sample_count=len(pairs),
    )
