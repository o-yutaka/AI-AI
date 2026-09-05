from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from research_bundle.models import KnowledgeMaterial, ResearchDecisionRecord

from .competition_objective import (
    CompetitionCandidateProfile,
    CompetitionPortfolioSelection,
    select_private_robust_portfolio,
)
from .winning_pipeline import WinningStrategyResult


@dataclass(frozen=True)
class ChampionshipResult:
    winning_strategy: WinningStrategyResult
    competition_selection: CompetitionPortfolioSelection
    decision: ResearchDecisionRecord
    knowledge_materials: tuple[KnowledgeMaterial, ...]


def select_championship_portfolio(
    winning_strategy: WinningStrategyResult,
    competition_profiles: Sequence[CompetitionCandidateProfile],
    *,
    runtime_budget_by_model: Mapping[str, float],
    max_candidates_per_model: int | None = None,
) -> ChampionshipResult:
    """Select a private-robust portfolio only from candidates that passed hard gates."""

    assessments = {
        assessment.candidate_id: assessment
        for assessment in winning_strategy.assessments
    }
    unknown = sorted(
        profile.candidate_id
        for profile in competition_profiles
        if profile.candidate_id not in assessments
    )
    if unknown:
        raise ValueError(
            "competition profiles are not bound to winning-strategy assessments: "
            + ",".join(unknown)
        )

    eligible_profiles = [
        profile
        for profile in competition_profiles
        if assessments[profile.candidate_id].eligible
    ]
    selection = select_private_robust_portfolio(
        eligible_profiles,
        runtime_budget_by_model=runtime_budget_by_model,
        max_candidates_per_model=max_candidates_per_model,
    )

    selected = set(selection.selected_candidate_ids)
    considered = sorted(profile.candidate_id for profile in competition_profiles)
    rejected = sorted(candidate_id for candidate_id in considered if candidate_id not in selected)
    decision = ResearchDecisionRecord(
        decision_id="research-decision::private-objective-portfolio",
        stage="private_portfolio_selection",
        candidates_considered=considered,
        selected=list(selection.selected_candidate_ids),
        rejected=rejected,
        rationale=(
            "selected only among candidates passing exact replay/runtime gates, then maximized "
            "expected private replay-weighted official score gain per runtime second; public "
            "leaderboard score is intentionally not an optimization input"
        ),
        evidence_refs=[],
        budget_units_spent=0.0,
    )

    materials = tuple(
        _selection_material(model_id, selection)
        for model_id in sorted(selection.selected_by_model)
    )
    return ChampionshipResult(
        winning_strategy=winning_strategy,
        competition_selection=selection,
        decision=decision,
        knowledge_materials=materials,
    )


def _selection_material(
    model_id: str,
    selection: CompetitionPortfolioSelection,
) -> KnowledgeMaterial:
    selected = selection.selected_by_model[model_id]
    return KnowledgeMaterial(
        material_id=f"championship-selection::{model_id}",
        kind="SEARCH_DECISION",
        subject_ref=model_id,
        statement=(
            "private-robust competition portfolio selected from hard-gated candidates using "
            "expected official-score marginal gain per runtime second"
        ),
        evidence_refs=[],
        metrics={
            "expected_private_raw_score": selection.expected_raw_score_by_model[model_id],
            "expected_private_normalized_score": (
                selection.expected_normalized_score_by_model[model_id]
            ),
            "planned_runtime_seconds": selection.runtime_seconds_by_model[model_id],
            "selected_candidate_count": float(len(selected)),
        },
        tags=["championship", "private_objective", "public_score_absent"],
        confidence=0.75,
    )
