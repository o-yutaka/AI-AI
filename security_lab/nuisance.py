from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class SweepCase:
    case_id: str
    values: Mapping[str, str]


def build_sweep(space: Mapping[str, Sequence[str]]) -> tuple[SweepCase, ...]:
    names = tuple(sorted(space))
    if any(len(space[name]) == 0 for name in names):
        raise ValueError("every sweep dimension requires at least one value")
    cases = []
    for index, values in enumerate(product(*(space[name] for name in names))):
        cases.append(
            SweepCase(
                f"case-{index:05d}",
                dict(zip(names, values, strict=True)),
            )
        )
    return tuple(cases)
