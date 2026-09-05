from __future__ import annotations

import json
from pathlib import Path

from security_lab.championship_io import championship_result_payload, run_championship_from_mapping


def test_championship_example_selects_private_stable_candidate() -> None:
    raw = json.loads(
        Path("examples/championship-strategy.example.json").read_text(encoding="utf-8")
    )
    result = run_championship_from_mapping(raw)
    payload = championship_result_payload(result)

    assert payload["private_objective"]["selected_candidate_ids"] == ["private-stable"]
    assert payload["research_decision"]["authority"] == "NONE"
