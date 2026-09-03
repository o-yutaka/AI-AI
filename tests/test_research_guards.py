import pytest

from security_lab import (
    BudgetLedger,
    BudgetStage,
    ResearchPurpose,
    Split,
    allocate_budget,
    assert_disjoint_instance_sets,
    assert_split_allowed,
)


def test_discovery_cannot_consume_held_out() -> None:
    with pytest.raises(ValueError, match="split leakage guard"):
        assert_split_allowed(ResearchPurpose.DISCOVERY, Split.HELD_OUT)


def test_validation_only_consumes_held_out() -> None:
    assert_split_allowed(ResearchPurpose.VALIDATION, Split.HELD_OUT)
    with pytest.raises(ValueError, match="split leakage guard"):
        assert_split_allowed(ResearchPurpose.VALIDATION, Split.DEV)


def test_instance_sets_must_be_disjoint() -> None:
    with pytest.raises(ValueError, match="dataset split leakage detected"):
        assert_disjoint_instance_sets(["a", "b"], ["b", "c"])


def test_budget_ledger_blocks_stage_overspend() -> None:
    ledger = BudgetLedger(allocate_budget(100))
    ledger.charge(BudgetStage.OPTIMIZATION, 20)
    ledger.charge(BudgetStage.OPTIMIZATION, 15)
    assert ledger.remaining(BudgetStage.OPTIMIZATION) == 0
    with pytest.raises(ValueError, match="research budget exceeded"):
        ledger.charge(BudgetStage.OPTIMIZATION, 0.1)
