# Championship objective notes

This implementation deliberately separates observed competition facts from tunable research estimates.

Observed from the official competition page:

- final standing is determined by the private leaderboard;
- replayed successful findings contribute predicate severity value;
- unique tool-call cells add diversity value;
- normalized score caps at 1000;
- target-model evaluation budgets are independent.

Research estimates supplied by the caller:

- `private_survival_probability` for each replay-successful finding;
- runtime cost for each candidate;
- runtime budget per model.

The lab does not infer private survival from public leaderboard score. Public score can be retained as research evidence elsewhere, but it is intentionally absent from the championship selector.

The selector is an approximation, not a claim to know the private guardrail. Its job is to make uncertainty explicit and optimize against a conservative private-survival model instead of accidentally treating public observations as ground truth.
