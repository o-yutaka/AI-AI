from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class RuntimeVariant:
    model_id: str
    runtime_id: str
    compiler_id: str
    quantization: str


@dataclass(frozen=True)
class RuntimeMatrix:
    variants: tuple[RuntimeVariant, ...]


def build_runtime_matrix(
    *,
    model_ids: Iterable[str],
    runtime_ids: Iterable[str],
    compiler_ids: Iterable[str],
    quantizations: Iterable[str],
) -> RuntimeMatrix:
    variants = tuple(
        RuntimeVariant(*values)
        for values in sorted(
            product(model_ids, runtime_ids, compiler_ids, quantizations)
        )
    )
    return RuntimeMatrix(variants)
