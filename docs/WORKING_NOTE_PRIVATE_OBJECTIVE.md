# Working Note: Selection, not public score, is the optimization problem

A robust multi-step tool-attack searcher has two distinct jobs: discover replayable failures and decide which discovered candidates deserve scarce evaluation runtime. Treating those as one objective encourages public-guardrail overfitting.

Our selection layer therefore applies hard replay and runtime-stability gates first. Only surviving candidates enter a second-stage objective that approximates private leaderboard value.

For each replay-successful finding we retain the predicate severity, a tool-call cell signature, runtime cost, and an evidence-derived estimate that the finding survives a stricter unseen guardrail. Expected severity value is linear in that survival estimate. Diversity is handled at the cell level rather than the finding level: if several findings occupy the same cell, their expected unique-cell value is `1 - product(1 - p_i)`. This prevents duplicate candidates from appearing more diverse than they are.

Candidate selection is then a budgeted marginal-gain problem. Within each target model's runtime budget, the selector repeatedly chooses the candidate with the largest increase in expected private raw score per runtime second. Public leaderboard score is not an input to this final selector.

This design does not claim to know the hidden guardrail. The private-survival estimate is explicit research material and can be stress-tested, calibrated, or replaced. The key methodological choice is that uncertainty is represented directly rather than silently equating public success with private success.

All outputs remain benchmark research artifacts. They do not authorize deployment or actions outside the controlled competition environment.
