from security_lab import CompetitionSpec, build_research_plan


def _plan():
    return build_research_plan(
        competition=CompetitionSpec(
            platform="kaggle",
            slug="ai-agent-security-multi-step-tool-attacks",
            name="AI Agent Security - Multi-Step Tool Attacks",
            evaluator_version="test-v1",
            tool_schema={"tools": []},
            time_budget_seconds=60,
            internet_enabled=False,
        ),
        dataset_id="dataset-a",
        source_revision="rev-1",
        instance_ids=["i3", "i1", "i2"],
        total_budget_units=100,
        model_ids=["model-b", "model-a"],
        runtime_ids=["runtime-a"],
        compiler_ids=["generic-chat.v1"],
        quantizations=["bf16", "q8"],
    )


def test_research_plan_is_deterministic() -> None:
    assert _plan() == _plan()


def test_research_plan_freezes_runtime_matrix_and_budget() -> None:
    plan = _plan()
    assert plan.plan_id.startswith("research-plan-")
    assert len(plan.runtime_matrix.variants) == 4
    assert plan.budget.optimization == 35
    assert plan.dataset.manifest_sha256
