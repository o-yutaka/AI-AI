from __future__ import annotations

import json
from pathlib import Path

from security_lab.championship_io import championship_result_payload, run_championship_from_mapping
from security_lab.championship_risk_io import (
    risk_championship_result_payload,
    run_risk_championship_from_mapping,
)


def test_championship_example_selects_private_stable_candidate() -> None:
    raw = json.loads(
        Path("examples/championship-strategy.example.json").read_text(encoding="utf-8")
    )
    result = run_championship_from_mapping(raw)
    payload = championship_result_payload(result)

    assert payload["private_objective"]["selected_candidate_ids"] == ["private-stable"]
    assert payload["research_decision"]["authority"] == "NONE"


def test_championship_risk_example_applies_wall_and_private_scenarios() -> None:
    raw = json.loads(Path("examples/championship-risk.example.json").read_text(encoding="utf-8"))
    result = run_risk_championship_from_mapping(raw)
    payload = risk_championship_result_payload(result)

    risk = payload["championship_risk"]
    assert risk["selected_candidate_ids"] == ["private-stable"]
    assert risk["replay_wall_plans"]["example-model"]["max_candidates"] == 1
    assert risk["selected_forfeit_probability_by_model"]["example-model"] == 0.0
    assert payload["research_decision"]["authority"] == "NONE"
