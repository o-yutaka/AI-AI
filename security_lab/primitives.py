from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompositionKind(str, Enum):
    SEQUENTIAL = "SEQUENTIAL"
    CONDITIONAL = "CONDITIONAL"
    SECOND_ORDER = "SECOND_ORDER"


@dataclass(frozen=True)
class AttackPrimitive:
    primitive_id: str
    family_id: str
    surface: str
    operator: str
    precondition: str
    expected_observable: str


@dataclass(frozen=True)
class PrimitiveComposition:
    composition_id: str
    kind: CompositionKind
    primitive_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.primitive_ids:
            raise ValueError("composition requires at least one primitive")
        if len(set(self.primitive_ids)) != len(self.primitive_ids):
            raise ValueError("composition primitive IDs must be unique")
