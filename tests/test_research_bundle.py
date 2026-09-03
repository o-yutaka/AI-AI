from datetime import UTC, datetime

from research_bundle import (
    CompetitionIdentity,
    Hypothesis,
    SecurityResearchBundle,
    bundle_sha256,
)


def make_bundle() -> SecurityResearchBundle:
    return SecurityResearchBundle(
        competition=CompetitionIdentity(
            competition_slug="ai-agent-security-multi-step-tool-attacks",
            competition_name="AI Agent Security - Multi-Step Tool Attacks",
        ),
        generated_at=datetime(2026, 9, 3, tzinfo=UTC),
        hypotheses=[
            Hypothesis(
                hypothesis_id="hyp-001",
                family="confused-deputy",
                statement=(
                    "A minimal benign-looking delegated action may transfer "
                    "differently across guardrails."
                ),
                falsification_condition=(
                    "No held evaluator observation distinguishes the family "
                    "from baseline."
                ),
            )
        ],
    )


def test_bundle_hash_is_deterministic() -> None:
    assert bundle_sha256(make_bundle()) == bundle_sha256(make_bundle())


def test_bundle_is_research_only() -> None:
    payload = make_bundle().model_dump(mode="json")
    forbidden = {
        "experience",
        "lesson",
        "adoption_authorized",
        "execution_authorized",
        "promotion_ready",
        "independently_verified",
    }
    assert forbidden.isdisjoint(payload.keys())
    assert payload["schema_version"] == "security-research-bundle.v1"
