from datetime import UTC, datetime

from research_bundle import (
    CompetitionIdentity,
    EnvironmentRecord,
    KnowledgeMaterial,
    ResearchDecisionRecord,
    SecurityResearchBundleV2,
    bundle_sha256,
)


def make_bundle() -> SecurityResearchBundleV2:
    return SecurityResearchBundleV2(
        competition=CompetitionIdentity(
            competition_slug="ai-agent-security-multi-step-tool-attacks",
            competition_name="AI Agent Security - Multi-Step Tool Attacks",
        ),
        generated_at=datetime(2026, 9, 4, tzinfo=UTC),
        knowledge_materials=[
            KnowledgeMaterial(
                material_id="material::runtime-1",
                kind="RUNTIME_SENSITIVITY",
                subject_ref="candidate::a",
                statement="candidate behavior changed across recorded runtimes",
                evidence_refs=["observation::1", "observation::2"],
                environment_refs=["env::proxy", "env::target"],
                metrics={"score_range": 0.2},
                confidence=0.8,
            )
        ],
        research_decisions=[
            ResearchDecisionRecord(
                decision_id="research-decision::1",
                stage="family-elimination",
                candidates_considered=["family-a", "family-b"],
                selected=["family-a"],
                rejected=["family-b"],
                rationale="family-b failed the frozen replay gate",
                evidence_refs=["observation::3"],
                budget_units_spent=2.0,
            )
        ],
        environments=[
            EnvironmentRecord(
                environment_id="env::target",
                model_id="example-model",
                runtime_id="target-runtime",
                compiler_id="generic-chat.v1",
                runtime_version="1.0.0",
            )
        ],
    )


def test_v2_hash_is_deterministic() -> None:
    assert bundle_sha256(make_bundle()) == bundle_sha256(make_bundle())


def test_v2_preserves_negative_and_environment_material() -> None:
    payload = make_bundle().model_dump(mode="json")
    assert payload["schema_version"] == "security-research-bundle.v2"
    assert payload["knowledge_materials"][0]["kind"] == "RUNTIME_SENSITIVITY"
    assert payload["research_decisions"][0]["rejected"] == ["family-b"]
    assert payload["environments"][0]["runtime_version"] == "1.0.0"


def test_v2_still_has_zero_black_authority_vocabulary() -> None:
    payload = make_bundle().model_dump(mode="json")
    forbidden = {
        "experience",
        "lesson",
        "adoption_authorized",
        "execution_authorized",
        "promotion_ready",
    }
    assert forbidden.isdisjoint(payload.keys())
    assert payload["research_decisions"][0]["authority"] == "NONE"
    assert payload["knowledge_materials"][0]["independently_verified"] is False
