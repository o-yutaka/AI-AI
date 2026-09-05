from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .championship import ChampionshipResult, select_championship_portfolio
from .competition_objective import (
    CompetitionCandidateProfile,
    CompetitionFindingSignal,
    SecurityPredicate,
)
from .sdk_runtime_contract import (
    championship_replay_budgets,
    kaggle_host_faq_contract,
    runtime_contract_from_mapping,
)
from .winning_io import rank_winning_portfolio_from_mapping, winning_strategy_result_payload


def run_championship_from_mapping(raw: Mapping[str, Any]) -> ChampionshipResult:
    winning_raw = _mapping(raw["winning_strategy"])
    winning_strategy = rank_winning_portfolio_from_mapping(winning_raw)
    profiles = [
        _competition_profile(_mapping(item))
        for item in _sequence(raw["competition_profiles"])
    ]
    runtime_budget_by_model = _resolve_runtime_budgets(raw, profiles)
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


def _resolve_runtime_budgets(
    raw: Mapping[str, Any],
    profiles: Sequence[CompetitionCandidateProfile],
) -> dict[str, float]:
    explicit = raw.get("runtime_budget_by_model")
    contract_raw = raw.get("runtime_contract")
    profile_name = raw.get("runtime_contract_profile")
    provided = sum(value is not None for value in (explicit, contract_raw, profile_name))
    if provided > 1:
        raise ValueError(
            "provide either runtime_budget_by_model or runtime_contract, "
            "or runtime_contract_profile; not more than one"
        )
    if explicit is not None:
        return {
            str(model_id): float(value)
            for model_id, value in _mapping(explicit).items()
        }
    if contract_raw is not None:
        contract = runtime_contract_from_mapping(dict(_mapping(contract_raw)))
    elif profile_name is not None:
        if str(profile_name) != "kaggle-host-faq-9000-v1":
            raise ValueError(f"unknown runtime contract profile: {profile_name}")
        contract = kaggle_host_faq_contract()
    else:
        raise ValueError("championship run requires runtime budget information")

    policy = _mapping(raw.get("runtime_policy", {}))
    return championship_replay_budgets(
        contract,
        model_ids=tuple(profile.model_id for profile in profiles),
        reserve_seconds=float(policy.get("reserve_seconds", 0.0)),
        reserve_fraction=float(policy.get("reserve_fraction", 0.0)),
    )


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
