from security_lab import (
    EnvironmentIdentity,
    Hypothesis,
    HypothesisGraph,
    JudgeThresholds,
    Observation,
    ProbeVerdict,
    RobustnessSample,
    Split,
    TransferPair,
    build_robustness_envelope,
    compile_probe,
    fit_linear_transfer,
    rank_and_judge,
    replay_probe,
    score_families,
)


def test_probe_is_deterministic() -> None:
    hypothesis = Hypothesis("h1", "family-a", "x", "not x", "signal")
    first = compile_probe(hypothesis, {"b": 2, "a": 1})
    second = compile_probe(hypothesis, {"a": 1, "b": 2})
    assert first.probe_id == second.probe_id


def test_replay_captures_observation_and_trajectory() -> None:
    hypothesis = Hypothesis("h1", "family-a", "x", "not x", "signal")
    probe = compile_probe(hypothesis, {"case": "safe-synthetic"})
    environment = EnvironmentIdentity("model", "runtime")

    def executor(_probe):
        return (
            "signal",
            ProbeVerdict.SUPPORTED,
            [{"step": "observe"}],
            {"token_count": 4, "latency_ms": 2},
        )

    replay = replay_probe(probe, environment, executor)
    assert replay.observation.verdict is ProbeVerdict.SUPPORTED
    assert replay.trajectory.token_count == 4
    assert replay.observation.evidence_refs == (replay.trajectory.trajectory_id,)


def test_family_elimination_and_held_out_judge() -> None:
    hypotheses = [
        Hypothesis("h1", "survivor", "x", "not x", "signal"),
        Hypothesis("h2", "drop", "y", "not y", "signal"),
    ]
    graph = HypothesisGraph(hypotheses)
    observations = [
        Observation("o1", "h1::a", "signal", ProbeVerdict.SUPPORTED),
        Observation("o2", "h1::b", "signal", ProbeVerdict.SUPPORTED),
        Observation("o3", "h2::a", "none", ProbeVerdict.REFUTED),
        Observation("o4", "h2::b", "none", ProbeVerdict.REFUTED),
    ]
    families = {
        item.family_id: item for item in score_families(graph, observations)
    }
    assert families["survivor"].eliminated is False
    assert families["drop"].eliminated is True

    envelope = build_robustness_envelope(
        [
            RobustnessSample("c1", 1.0, True, 0.4),
            RobustnessSample("c2", 0.9, True, 0.3),
        ]
    )
    decisions = rank_and_judge(
        hypotheses,
        observations,
        {"survivor": envelope, "drop": envelope},
        split=Split.HELD_OUT,
        thresholds=JudgeThresholds(
            minimum_success_rate=1.0,
            minimum_margin=0.2,
        ),
    )
    by_family = {item.family.family_id: item for item in decisions}
    assert by_family["survivor"].judge.verdict == "VERIFIED_FOR_RESEARCH"
    assert by_family["drop"].judge.verdict == "REJECTED"


def test_transfer_calibrator_tracks_proxy_target_drift() -> None:
    estimate = fit_linear_transfer(
        [
            TransferPair(0.0, 1.0),
            TransferPair(1.0, 3.0),
            TransferPair(2.0, 5.0),
        ]
    )
    assert round(estimate.slope, 6) == 2.0
    assert round(estimate.intercept, 6) == 1.0
    assert round(estimate.predict(3.0), 6) == 7.0


def test_non_held_out_never_verifies_for_research() -> None:
    hypotheses = [Hypothesis("h1", "family-a", "x", "not x", "signal")]
    observations = [
        Observation("o1", "h1::a", "signal", ProbeVerdict.SUPPORTED),
        Observation("o2", "h1::b", "signal", ProbeVerdict.SUPPORTED),
    ]
    envelope = build_robustness_envelope(
        [RobustnessSample("c1", 1.0, True, 0.5)]
    )
    decision = rank_and_judge(
        hypotheses,
        observations,
        {"family-a": envelope},
        split=Split.DEV,
    )[0]
    assert decision.judge.verdict == "REJECTED"
    assert "not_held_out" in decision.judge.reason_codes
