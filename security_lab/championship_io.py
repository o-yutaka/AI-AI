from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .championship import ChampionshipResult, select_championship_portfolio
from .competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    SecurityPredicate,
)
from .winning_io import rank_winning_portfolio_from_mapping, winning_strategy_result_payload


def run_championship_from_mapping(raw: Mapping[str, Any]) -> ChampionshipResult:
    winning_raw = _mapping(raw["winning_strategy"])
    winning_strategy = rank_winning_portfolio_from_mapping(winning_raw)
    profiles = [
        _competition_profile(_mapping(item))
        for item in _sequence(raw["competition_profiles"])
    ]
    runtime_budget_by_model = {
        str(model_id): float(value)
        for model_id, value in _mapping(raw["runtime_budget_by_model"]).items()
    }
    maximum_raw = raw.get("max_candidates_per_model")
    maximum = int(maximum_raw) if maximum_raw is not None else None
    return select_championship_portfolio(
        winning_strategy,
        profiles,
        runtime_budget_by_model=runtime_budget_by_model,
        max_candidates_per_model=maximum,
    )


def championship_result_payload(result: ChampionshipResult) -> dict[str, Any]:
    selection = result.competition_selection
    return {
        "winning_strategy": winning_strategy_result_payload(result.winning_strategy),
        "private_objective": {
            "selected_candidate_ids": list(selection.selected_candidate_ids),
            "selected_by_model": {
                model_id: list(candidate_ids)
                for model_id, candidate_ids in selection.selected_by_model.items()
            },
            "expected_raw_score_by_model": dict(selection.expected_raw_score_by_model),
            "expected_normalized_score_by_model": dict(
                selection.expected_normalized_score_by_model
            ),
            "runtime_seconds_by_model": dict(selection.runtime_seconds_by_model),
        },
        "research_decision": result.decision.model_dump(mode="json"),
        "knowledge_materials": [
            item.model_dump(mode="json") for item in result.knowledge_materials
        ],
    }


def _competition_profile(raw: Mapping[str, Any]) -> CompetitionCandidateProfile:
    candidate_id = str(raw["candidate_id"])
    model_id = str(raw["model_id"])
    findings = tuple(
        _finding(candidate_id, model_id, _mapping(item))
        for item in _sequence(raw.get("findings", ()))
    )
    return CompetitionCandidateProfile(
        candidate_id=candidate_id,
        family_id=str(raw["family_id"]),
        model_id=model_id,
        runtime_seconds=float(raw["runtime_seconds"]),
        findings=findings,
    )


def _finding(
    candidate_id: str,
    model_id: str,
    raw: Mapping[str, Any],
) -> CompetitionFindingSignal:
    return CompetitionFindingSignal(
        candidate_id=str(raw.get("candidate_id", candidate_id)),
        model_id=str(raw.get("model_id", model_id)),
        predicate=SecurityPredicate(str(raw["predicate"])),
        severity=int(raw["severity"]),
        cell_signature=str(raw["cell_signature"]),
        replay_success=bool(raw["replay_success"]),
        private_survival_probability=float(
            raw.get("private_survival_probability", 1.0)
        ),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("expected JSON object")
    return value


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError("expected JSON array")
    return value
