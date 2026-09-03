from security_lab import (
    BudgetLedger,
    EnvironmentIdentity,
    ExperimentCase,
    Hypothesis,
    ProbeVerdict,
    ResearchPurpose,
    ResearchSession,
    Split,
    allocate_budget,
    load_records,
    verify_chain,
)


def _case(split: Split, budget_cost: float = 1.0) -> ExperimentCase:
    return ExperimentCase(
        hypothesis=Hypothesis(
            hypothesis_id="h1",
            family_id="family-1",
            statement="benign fixture produces expected observable",
            falsification_condition="expected observable missing",
            expected_observable="ok",
        ),
        split=split,
        instance_id="instance-1",
        payload={"fixture": "benign"},
        environment=EnvironmentIdentity(model_id="model-a", runtime_id="runtime-a"),
        budget_cost=budget_cost,
    )


def test_session_runs_and_records_hash_chained_provenance(tmp_path) -> None:
    path = tmp_path / "session-ledger.jsonl"
    session = ResearchSession(BudgetLedger(allocate_budget(100)), ledger_path=path)

    runs = session.run(
        ResearchPurpose.DISCOVERY,
        [_case(Split.DEV)],
        execute=lambda probe, _: (
            "ok",
            ProbeVerdict.SUPPORTED,
            [{"probe_id": probe.probe_id}],
            {"token_count": 1},
        ),
    )

    assert len(runs) == 1
    records = load_records(path)
    assert len(records) == 1
    assert records[0].record_type == "experiment_run"
    assert verify_chain(records) == records[0].record_hash


def test_session_rejects_held_out_discovery() -> None:
    session = ResearchSession(BudgetLedger(allocate_budget(100)))

    try:
        session.run(
            ResearchPurpose.DISCOVERY,
            [_case(Split.HELD_OUT)],
            execute=lambda probe, _: (
                "ok",
                ProbeVerdict.SUPPORTED,
                [{"probe_id": probe.probe_id}],
                {},
            ),
        )
    except ValueError as exc:
        assert "split leakage guard" in str(exc)
    else:
        raise AssertionError("held-out discovery must be rejected")
