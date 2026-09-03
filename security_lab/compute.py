from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ComputeTarget:
    name: str
    available: bool
    vram_gb: float | None
    remaining_minutes: int | None
    priority: int


@dataclass(frozen=True)
class ComputeRequest:
    required_vram_gb: float
    estimated_minutes: int


def select_compute_target(
    request: ComputeRequest,
    targets: Iterable[ComputeTarget],
) -> ComputeTarget:
    eligible: list[ComputeTarget] = []
    for target in targets:
        if not target.available:
            continue
        if target.vram_gb is not None and target.vram_gb < request.required_vram_gb:
            continue
        if (
            target.remaining_minutes is not None
            and target.remaining_minutes < request.estimated_minutes
        ):
            continue
        eligible.append(target)
    if not eligible:
        raise RuntimeError("no compute target satisfies the request")
    return sorted(
        eligible,
        key=lambda item: (
            item.priority,
            -(item.remaining_minutes if item.remaining_minutes is not None else 10**9),
            -(item.vram_gb if item.vram_gb is not None else 10**9),
            item.name,
        ),
    )[0]
