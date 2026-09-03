from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from .models import Split


class ResearchPurpose(StrEnum):
    DISCOVERY = "DISCOVERY"
    FALSIFICATION = "FALSIFICATION"
    OPTIMIZATION = "OPTIMIZATION"
    VALIDATION = "VALIDATION"
    ADVERSARIAL_VALIDATION = "ADVERSARIAL_VALIDATION"


_ALLOWED_SPLITS: dict[ResearchPurpose, frozenset[Split]] = {
    ResearchPurpose.DISCOVERY: frozenset({Split.TRAIN, Split.DEV}),
    ResearchPurpose.FALSIFICATION: frozenset({Split.TRAIN, Split.DEV}),
    ResearchPurpose.OPTIMIZATION: frozenset({Split.TRAIN, Split.DEV}),
    ResearchPurpose.VALIDATION: frozenset({Split.HELD_OUT}),
    ResearchPurpose.ADVERSARIAL_VALIDATION: frozenset(
        {Split.ADVERSARIAL_HELD_OUT}
    ),
}


def assert_split_allowed(purpose: ResearchPurpose, split: Split) -> None:
    if split not in _ALLOWED_SPLITS[purpose]:
        allowed = ",".join(
            sorted(item.value for item in _ALLOWED_SPLITS[purpose])
        )
        raise ValueError(
            f"split leakage guard: {purpose.value} cannot consume "
            f"{split.value}; allowed={allowed}"
        )


def assert_disjoint_instance_sets(
    training_ids: Iterable[str],
    held_out_ids: Iterable[str],
    adversarial_held_out_ids: Iterable[str] = (),
) -> None:
    train = set(training_ids)
    held = set(held_out_ids)
    adversarial = set(adversarial_held_out_ids)
    collisions = sorted(
        (train & held) | (train & adversarial) | (held & adversarial)
    )
    if collisions:
        raise ValueError(
            f"dataset split leakage detected: {','.join(collisions)}"
        )
