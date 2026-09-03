from dataclasses import replace

import pytest

from security_lab.failure_correlation import (
    FailureProfile,
    build_failure_correlation_graph,
    select_correlation_diverse_portfolio,
)
from security_lab.minimum_trace import TraceEvaluation, minimize_winning_trace
from security_lab.models import (
    EnvironmentIdentity,
    Observation,
    ProbeVerdict,
    Trajectory,
)
from security_lab.portfolio import CandidateProfile
from security_lab.replay import ReplayResult
from security_lab.target_gate import TargetReplayExpectation, evaluate_target_replay
from security_lab.transfer import TransferPair, fit_ridge_transfer


def _trajectory() -> Trajectory:
    return Trajectory(
        trajectory_id="trajectory::p1",
        probe_id="p1",
        environment=EnvironmentIdentity(
            model_id="model-a",
            runtime_id="runtime-a",
            quantization="target",
            evaluator_hash="e" * 64,
            runtime_version="1.2.3",
            compiler_id="compiler-a",
        ),
        steps=(
            {"kind": "required-step", "id": "first"},
            {"kind": "unnecessary-cleanup", "id": "second"},
        ),
        completed=True,
    )


def test_minimum_winning_trace_removes_unnecessary_suffix() -> None:
    trajectory = _trajectory()

    def evaluator(steps):
        has_required = any(step.get("kind") == "required-step" for step in steps)
        return TraceEvaluation(
            successful=has_required,
            output_valid=True,
            score=1.0 if has_required else 0.0,
        )

    result = minimize_winning_trace(
        trajectory,
        evaluator,
        minimum_prefix_steps=1,
    )
    assert result.original_step_count == 2
    assert result.winning_step_count == 1
    assert result.removed_step_count == 1
    assert result.replay_count == 2
    assert result.minimum_steps == (trajectory.steps[0],)


def test_minimum_winning_trace_requires_valid_baseline() -> None:
    with pytest.raises(ValueError, match="source trajectory"):
        minimize_winning_trace(
            _trajectory(),
            lambda _steps: TraceEvaluation(successful=False),
            minimum_prefix_steps=1,
        )


def test_exact_target_replay_gate_rejects_runtime_drift() -> None:
    trajectory = _trajectory()
    observation = Observation(
        observation_id="observation::p1",
        probe_id="p1",
        observable="tool-call",
        verdict=ProbeVerdict.SUPPORTED,
        evidence_refs=(trajectory.trajectory_id,),
    )
    replay = ReplayResult(observation=observation, trajectory=trajectory)
    expectation = TargetReplayExpectation(
        environment=trajectory.environment,
        required_observable="tool-call",
    )
    assert evaluate_target_replay(expectation, replay).passed is True

    drifted = replace(
        trajectory,
        environment=replace(trajectory.environment, runtime_version="1.2.4"),
    )
    verdict = evaluate_target_replay(
        expectation,
        ReplayResult(observation=observation, trajectory=drifted),
    )
    assert verdict.passed is False
    assert "environment_identity_mismatch" in verdict.reason_codes
    assert verdict.expected_environment_hash != verdict.observed_environment_hash


def test_ridge_transfer_matches_linear_when_alpha_zero_and_shrinks_slope() -> None:
    pairs = [
        TransferPair(0.0, 1.0),
        TransferPair(1.0, 3.0),
        TransferPair(2.0, 5.0),
    ]
    unregularized = fit_ridge_transfer(pairs, alpha=0.0)
    regularized = fit_ridge_transfer(pairs, alpha=1.0)

    assert unregularized.slope == pytest.approx(2.0)
    assert unregularized.intercept == pytest.approx(1.0)
    assert regularized.slope < unregularized.slope
    assert regularized.conservative_lower_bound(2.0) <= regularized.predict(2.0)


def test_failure_correlation_selector_avoids_duplicate_failure_modes() -> None:
    graph = build_failure_correlation_graph(
        [
            FailureProfile("a", (True, True, False, False)),
            FailureProfile("b", (True, True, False, False)),
            FailureProfile("c", (False, False, True, True)),
        ]
    )
    assert graph.correlation("a", "b") == pytest.approx(1.0)
    assert graph.correlation("a", "c") == pytest.approx(0.0)

    candidates = [
        CandidateProfile("a", "family-a", 10.0, 1.0, 1.0, "cluster-a"),
        CandidateProfile("b", "family-b", 9.0, 1.0, 1.0, "cluster-b"),
        CandidateProfile("c", "family-c", 8.0, 1.0, 1.0, "cluster-c"),
    ]
    selected = select_correlation_diverse_portfolio(
        candidates,
        graph,
        2,
        correlation_penalty=1.0,
    )
    assert [item.candidate_id for item in selected] == ["a", "c"]
