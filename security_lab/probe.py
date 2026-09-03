from __future__ import annotations

import json
from hashlib import sha256

from .models import Hypothesis, Probe, Split


def compile_probe(
    hypothesis: Hypothesis,
    payload: dict[str, object],
    *,
    split: Split = Split.DEV,
    budget_cost: float = 1.0,
) -> Probe:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    identity = f"{hypothesis.hypothesis_id}\n{split.value}\n{canonical}"
    digest = sha256(identity.encode()).hexdigest()[:16]
    return Probe(
        probe_id=f"{hypothesis.hypothesis_id}::{digest}",
        hypothesis_id=hypothesis.hypothesis_id,
        split=split,
        input_payload=dict(payload),
        expected_observable=hypothesis.expected_observable,
        budget_cost=budget_cost,
    )


def compile_minimal_falsification_probe(
    hypothesis: Hypothesis,
    *,
    split: Split = Split.DEV,
) -> Probe:
    return compile_probe(
        hypothesis,
        {
            "hypothesis_id": hypothesis.hypothesis_id,
            "falsification_condition": hypothesis.falsification_condition,
            "expected_observable": hypothesis.expected_observable,
        },
        split=split,
    )
