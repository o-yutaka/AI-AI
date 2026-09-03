from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from .models import Split


@dataclass(frozen=True)
class FrozenInstance:
    instance_id: str
    split: Split
    identity_hash: str


@dataclass(frozen=True)
class FrozenDataset:
    dataset_id: str
    source_revision: str
    instances: tuple[FrozenInstance, ...]
    manifest_sha256: str


def freeze_dataset(
    dataset_id: str,
    source_revision: str,
    instance_ids: Iterable[str],
    *,
    train_ratio: int = 60,
    dev_ratio: int = 20,
    held_out_ratio: int = 10,
) -> FrozenDataset:
    if train_ratio + dev_ratio + held_out_ratio >= 100:
        raise ValueError("split ratios must leave room for ADVERSARIAL_HELD_OUT")
    rows: list[FrozenInstance] = []
    for raw in sorted(set(instance_ids)):
        identity = hashlib.sha256(f"{dataset_id}:{source_revision}:{raw}".encode()).hexdigest()
        bucket = int(identity[:8], 16) % 100
        if bucket < train_ratio:
            split = Split.TRAIN
        elif bucket < train_ratio + dev_ratio:
            split = Split.DEV
        elif bucket < train_ratio + dev_ratio + held_out_ratio:
            split = Split.HELD_OUT
        else:
            split = Split.ADVERSARIAL_HELD_OUT
        rows.append(FrozenInstance(raw, split, identity))
    manifest = "\n".join(
        f"{row.instance_id}\t{row.split.value}\t{row.identity_hash}" for row in rows
    )
    manifest_hash = hashlib.sha256(manifest.encode()).hexdigest()
    return FrozenDataset(dataset_id, source_revision, tuple(rows), manifest_hash)
