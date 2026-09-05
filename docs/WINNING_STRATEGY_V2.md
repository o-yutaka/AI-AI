# Kaggle Winning Strategy v2

V2 changes the final optimization target from public-leaderboard score to a private-robust approximation of the competition's replayed objective.

## Why

The competition's official score rewards successful predicate severity plus unique tool-call cells. Final placement is determined by the private leaderboard, so a candidate that is spectacular only under the public guardrail can be worse than a lower-public-score candidate that survives stricter replay.

V2 therefore keeps the existing hard gates and adds a final competition-aware selector:

```text
family / hypothesis research
  -> semantic / optimizer search
  -> proxy-to-target calibration
  -> exact target replay gate
  -> runtime-sensitivity gate
  -> optional minimum winning trace
  -> eligible candidates only
  -> expected private survival
  -> severity-weighted finding value
  -> probabilistic unique-cell value
  -> marginal value per runtime second
  -> model-budgeted championship portfolio
```

## Expected private objective

For replay-successful findings, the selector computes:

```text
expected severity value
+ 2 * expected unique-cell count
```

Severity uses the competition weights `{1:1, 2:2, 3:4, 4:8, 5:16}` multiplied by an evidence-derived private-survival probability.

For duplicate cells, V2 does not simply count each finding. If several findings occupy the same cell, the unique-cell contribution is the probability that at least one survives:

```text
P(cell survives) = 1 - product(1 - p_i)
```

This preserves the competition's diversity incentive while avoiding double-counting correlated duplicates.

## Runtime allocation

Selection is performed independently per target model because evaluation budgets are model-scoped. Candidates are greedily chosen by marginal expected private raw-score gain per runtime second, subject to the configured budget.

The budget is configuration, not a hard-coded competition constant, so the lab remains usable when evaluator timing changes.

## One command

```bash
kaggle-security-lab championship-run examples/championship-strategy.example.json
```

The input contains the existing `winning_strategy` evidence block plus `competition_profiles` and `runtime_budget_by_model`.

## Boundary

`championship-run` is still research selection only.

```text
Kaggle championship selection != independent verification
Kaggle championship selection != BLACK Decision
Kaggle championship selection != adoption / promotion / routing / execution authority
```

The emitted `ResearchDecisionRecord` has `authority = NONE`. Research material may later enter BLACK through the neutral research-bundle boundary, where BLACK must perform its own Mission binding, provenance checks, Experience creation, held-out evaluation, and sovereign Decision.
