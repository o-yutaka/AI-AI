from security_lab.portfolio import CandidateProfile, select_diverse_portfolio


def test_portfolio_prefers_distinct_failure_clusters_before_duplicates() -> None:
    candidates = [
        CandidateProfile("a", "family-a", 10.0, 0.9, 1.0, "cluster-1"),
        CandidateProfile("b", "family-a", 9.5, 0.9, 1.0, "cluster-1"),
        CandidateProfile("c", "family-b", 8.0, 0.9, 1.0, "cluster-2"),
    ]
    selected = select_diverse_portfolio(candidates, 2)
    assert [item.candidate_id for item in selected] == ["a", "c"]


def test_portfolio_expected_value_includes_survival_and_throughput() -> None:
    candidates = [
        CandidateProfile("high-public-brittle", "family-a", 20.0, 0.1, 1.0, "cluster-1"),
        CandidateProfile("stable", "family-b", 8.0, 0.9, 1.0, "cluster-2"),
    ]
    selected = select_diverse_portfolio(candidates, 1)
    assert selected[0].candidate_id == "stable"
