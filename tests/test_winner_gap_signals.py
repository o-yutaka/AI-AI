import pytest

from security_lab.termination_economics import (
    TerminationRuntimeSample,
    analyze_termination_economics,
    post_success_capacity_gain,
)
from security_lab.timing_signal import (
    TimingOutcome,
    TimingSample,
    fit_timing_calibration,
    infer_timing_survival,
)


def test_timing_calibration_detects_fast_success_signal() -> None:
    samples = (
        TimingSample("s1", TimingOutcome.SUCCESS, 1.0, "env-a"),
        TimingSample("s2", TimingOutcome.SUCCESS, 1.1, "env-a"),
        TimingSample("s3", TimingOutcome.SUCCESS, 0.9, "env-a"),
        TimingSample("b1", TimingOutcome.BLOCKED, 8.0, "env-a"),
        TimingSample("b2", TimingOutcome.BLOCKED, 8.2, "env-a"),
        TimingSample("b3", TimingOutcome.BLOCKED, 7.8, "env-a"),
    )
    calibration = fit_timing_calibration(samples, minimum_separation_s=1.0)
    report = infer_timing_survival(
        calibration,
        (1.0, 1.2, 1.1),
        environment_key="env-a",
    )
    assert calibration.success_is_faster is True
    assert report.conservative_success_probability > 0.9


def test_timing_calibration_can_detect_slow_success_signal() -> None:
    samples = (
        TimingSample("s1", TimingOutcome.SUCCESS, 8.0, "env-a"),
        TimingSample("s2", TimingOutcome.SUCCESS, 8.1, "env-a"),
        TimingSample("s3", TimingOutcome.SUCCESS, 7.9, "env-a"),
        TimingSample("b1", TimingOutcome.BLOCKED, 1.0, "env-a"),
        TimingSample("b2", TimingOutcome.BLOCKED, 1.1, "env-a"),
        TimingSample("b3", TimingOutcome.BLOCKED, 0.9, "env-a"),
    )
    calibration = fit_timing_calibration(samples)
    report = infer_timing_survival(
        calibration,
        (8.0, 7.8),
        environment_key="env-a",
    )
    assert calibration.success_is_faster is False
    assert report.mean_success_probability > 0.9


def test_timing_calibration_rejects_environment_mixing_and_weak_separation() -> None:
    with pytest.raises(ValueError, match="mix environment"):
        fit_timing_calibration(
            (
                TimingSample("s1", TimingOutcome.SUCCESS, 1.0, "env-a"),
                TimingSample("s2", TimingOutcome.SUCCESS, 1.1, "env-a"),
                TimingSample("s3", TimingOutcome.SUCCESS, 0.9, "env-a"),
                TimingSample("b1", TimingOutcome.BLOCKED, 8.0, "env-b"),
                TimingSample("b2", TimingOutcome.BLOCKED, 8.1, "env-b"),
                TimingSample("b3", TimingOutcome.BLOCKED, 7.9, "env-b"),
            )
        )

    with pytest.raises(ValueError, match="separation is too small"):
        fit_timing_calibration(
            (
                TimingSample("s1", TimingOutcome.SUCCESS, 1.00, "env-a"),
                TimingSample("s2", TimingOutcome.SUCCESS, 1.02, "env-a"),
                TimingSample("s3", TimingOutcome.SUCCESS, 0.98, "env-a"),
                TimingSample("b1", TimingOutcome.BLOCKED, 1.05, "env-a"),
                TimingSample("b2", TimingOutcome.BLOCKED, 1.06, "env-a"),
                TimingSample("b3", TimingOutcome.BLOCKED, 1.04, "env-a"),
            ),
            minimum_separation_s=0.1,
        )


def test_timing_inference_rejects_cross_environment_use() -> None:
    calibration = fit_timing_calibration(
        (
            TimingSample("s1", TimingOutcome.SUCCESS, 1.0, "env-a"),
            TimingSample("s2", TimingOutcome.SUCCESS, 1.1, "env-a"),
            TimingSample("s3", TimingOutcome.SUCCESS, 0.9, "env-a"),
            TimingSample("b1", TimingOutcome.BLOCKED, 8.0, "env-a"),
            TimingSample("b2", TimingOutcome.BLOCKED, 8.1, "env-a"),
            TimingSample("b3", TimingOutcome.BLOCKED, 7.9, "env-a"),
        )
    )
    with pytest.raises(ValueError, match="does not match calibration"):
        infer_timing_survival(calibration, (1.0,), environment_key="env-b")


def test_termination_economics_preserves_success_before_optimizing_cost() -> None:
    result = analyze_termination_economics(
        (
            TerminationRuntimeSample("fast-fragile", "runtime-a", True, 1, 0.1, 6.0),
            TerminationRuntimeSample("fast-fragile", "runtime-b", False, 1, 0.1, 6.0),
            TerminationRuntimeSample("stable", "runtime-a", True, 2, 0.2, 7.0),
            TerminationRuntimeSample("stable", "runtime-b", True, 2, 0.2, 6.5),
            TerminationRuntimeSample("slow", "runtime-a", True, 20, 1.0, 8.0),
            TerminationRuntimeSample("slow", "runtime-b", True, 20, 1.1, 8.0),
        ),
        token_seconds=0.01,
        minimum_eog_margin=5.0,
    )
    assert result.selected_candidate_id == "stable"
    reports = {item.candidate_id: item for item in result.reports}
    assert reports["fast-fragile"].eligible is False
    assert "successful_action_not_preserved_on_all_runtimes" in reports[
        "fast-fragile"
    ].rejection_reasons


def test_termination_economics_fails_closed_when_margin_is_missing() -> None:
    result = analyze_termination_economics(
        (
            TerminationRuntimeSample("candidate", "runtime-a", True, 1, 0.1, None),
        ),
        minimum_eog_margin=1.0,
    )
    assert result.selected_candidate_id is None
    assert result.reports[0].rejection_reasons == ("eog_margin_missing",)


def test_post_success_capacity_gain_quantifies_saved_replay_slots() -> None:
    assert post_success_capacity_gain(
        baseline_cost_s=3.0,
        optimized_cost_s=2.0,
        replay_budget_s=9_000.0,
    ) == 1_500
