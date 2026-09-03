from security_lab import (
    CandidateRecord,
    EnvironmentIdentity,
    ExperimentCase,
    Hypothesis,
    ProbeVerdict,
    Split,
    allocate_budget,
    freeze_dataset,
    package_candidates,
    run_cases,
)


def test_budget_allocation_is_canonical() -> None:
    plan = allocate_budget(100)
    assert plan.evaluator_identification == 25
    assert plan.falsification == 25
    assert plan.optimization == 35
    assert plan.portfolio_validation == 15


def test_dataset_freeze_is_deterministic_and_disjoint() -> None:
    left = freeze_dataset("demo", "rev-1", ["c", "a", "b", "a"])
    right = freeze_dataset("demo", "rev-1", ["a", "b", "c"])
    assert left == right
    assert len(left.instances) == 3
    assert len({item.instance_id for item in left.instances}) == 3
    assert all(item.identity_hash for item in left.instances)


def test_candidate_package_is_order_independent() -> None:
    a = CandidateRecord("a", "family-a", "generic-chat.v1", "0" * 64, "cluster-a", 1.0, 0.8, 10.0)
    b = CandidateRecord("b", "family-b", "generic-chat.v1", "1" * 64, "cluster-b", 0.9, 0.9, 12.0)
    assert package_candidates([a, b]) == package_candidates([b, a])


def test_runner_binds_split_and_environment_to_replay() -> None:
    hypothesis = Hypothesis(
        hypothesis_id="h1",
        family_id="family-1",
        statement="observable behavior differs by evaluator state",
        falsification_condition="expected observable is absent",
        expected_observable="tool-call",
    )
    environment = EnvironmentIdentity(model_id="model-a", runtime_id="runtime-a")
    case = ExperimentCase(
        hypothesis=hypothesis,
        split=Split.HELD_OUT,
        instance_id="instance-1",
        payload={"input": "benign research probe"},
        environment=environment,
    )

    runs = run_cases(
        [case],
        execute=lambda probe, _: (
            "tool-call",
            ProbeVerdict.SUPPORTED,
            [{"kind": "model-output", "probe_id": probe.probe_id}],
            {"token_count": 7, "latency_ms": 3},
        ),
    )

    assert len(runs) == 1
    run = runs[0]
    assert run.probe.split is Split.HELD_OUT
    assert run.replay.trajectory.environment == environment
    assert run.replay.observation.evidence_refs == (run.replay.trajectory.trajectory_id,)
