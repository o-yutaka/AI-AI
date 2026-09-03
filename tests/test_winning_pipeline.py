from security_lab.minimum_trace import TraceEvaluation
from security_lab.models import EnvironmentIdentity, Observation, ProbeVerdict, Trajectory
from security_lab.replay import ReplayResult
from security_lab.runtime_matrix import RuntimeVariant
from security_lab.runtime_sensitivity import RuntimeOutcome
from security_lab.target_gate import TargetReplayExpectation
from security_lab.transfer import TransferPair
from security_lab.winning_pipeline import WinningCandidateEvidence, rank_winning_portfolio


def _environment() -> EnvironmentIdentity:
    return EnvironmentIdentity(
        model_id="model",
        runtime_id="target-runtime",
        quantization="target",
        evaluator_hash="e" * 64,
        runtime_version="1.0.0",
        compiler_id="compiler",
    )


def _evidence(
    candidate_id: str,
    proxy_score: float,
    failures: tuple[bool, ...],
) -> WinningCandidateEvidence:
    trajectory = Trajectory(
        trajectory_id=f"trajectory::{candidate_id}",
        probe_id=f"probe::{candidate_id}",
        environment=_environment(),
        steps=(
            {"kind": "required-step"},
            {"kind": "optional-suffix"},
        ),
    )
    observation = Observation(
        observation_id=f"observation::{candidate_id}",
        probe_id=trajectory.probe_id,
        observable="expected",
        verdict=ProbeVerdict.SUPPORTED,
        evidence_refs=(trajectory.trajectory_id,),
    )
    return WinningCandidateEvidence(
        candidate_id=candidate_id,
        family_id=f"family::{candidate_id}",
        proxy_score=proxy_score,
        target_replay=ReplayResult(observation, trajectory),
        runtime_outcomes=(
            RuntimeOutcome(
                candidate_id,
                RuntimeVariant("model", "target-runtime", "compiler", "target"),
                proxy_score,
                True,
            ),
        ),
        failures=failures,
        throughput=1.0,
    )


def test_winning_pipeline_combines_transfer_trace_runtime_and_diversity() -> None:
    evidence = [
        _evidence("a", 10.0, (True, True, False, False)),
        _evidence("b", 9.0, (True, True, False, False)),
        _evidence("c", 8.0, (False, False, True, True)),
    ]

    result = rank_winning_portfolio(
        evidence,
        transfer_pairs=[TransferPair(0.0, 0.0), TransferPair(10.0, 10.0)],
        target_expectation=TargetReplayExpectation(
            _environment(),
            required_observable="expected",
        ),
        portfolio_limit=2,
        ridge_alpha=0.0,
        correlation_penalty=1.0,
        trace_evaluator=lambda _candidate_id, steps: TraceEvaluation(
            successful=any(step.get("kind") == "required-step" for step in steps),
            output_valid=True,
        ),
        minimum_prefix_steps=1,
    )

    assert result.selected_candidate_ids == ("a", "c")
    assert all(item.eligible for item in result.assessments)
    assert all(item.minimum_trace is not None for item in result.assessments)
    assert all(item.minimum_trace.winning_step_count == 1 for item in result.assessments)


def test_winning_pipeline_rejects_exact_target_environment_drift() -> None:
    item = _evidence("a", 1.0, (False,))
    result = rank_winning_portfolio(
        [item],
        transfer_pairs=[TransferPair(0.0, 0.0), TransferPair(1.0, 1.0)],
        target_expectation=TargetReplayExpectation(
            EnvironmentIdentity(
                model_id="model",
                runtime_id="target-runtime",
                quantization="target",
                evaluator_hash="e" * 64,
                runtime_version="2.0.0",
                compiler_id="compiler",
            )
        ),
        portfolio_limit=1,
        ridge_alpha=0.0,
    )

    assert result.selected_candidate_ids == ()
    assert result.assessments[0].eligible is False
    assert "environment_identity_mismatch" in result.assessments[0].reason_codes
