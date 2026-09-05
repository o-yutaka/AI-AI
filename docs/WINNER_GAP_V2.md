# Winner-gap v2: atomic replay-wall risk + private guardrail scenarios

This layer closes two championship-planning gaps left after timing calibration and post-success termination economics.

## 1. Atomic replay wall is not ordinary runtime cost

A hosted evaluator can behave as an all-or-nothing wall: a model phase that completes contributes its replayed findings, while a phase that overruns its budget may forfeit the phase. Optimizing only `score / runtime_second` can therefore select too many individually attractive candidates and create a catastrophic portfolio-level loss.

`replay_wall.py` treats observed COMPLETE/FORFEIT runs as censored evidence:

```text
COMPLETE at N candidates => average replay cost <= budget / N
FORFEIT  at N candidates => average replay cost >  budget / N
```

The result is an interval, not a fabricated point estimate. Planning uses an explicitly named uniform-interval assumption to estimate forfeit probability and derive the largest candidate count that satisfies a caller-owned risk target.

Important properties:

- exact environment identity is mandatory;
- mixed environments fail closed;
- contradictory bounds fail closed;
- no finite upper bound means no calibration unless the caller supplies an explicit prior ceiling;
- the probability model is labeled as a planning assumption, not evaluator truth.

## 2. One private-survival scalar can hide opposite failure modes

Different candidate families can transfer differently when hidden guardrail behavior changes. Collapsing all uncertainty into one scalar can make a portfolio look strong while every candidate shares the same hidden failure mode.

`guardrail_scenarios.py` keeps multiple private scenarios explicit. Each candidate supplies evidence-bound survival per scenario. The objective blends:

```text
robust_score
  = (1 - risk_aversion) * weighted_expected_score
  + risk_aversion * worst_case_score
```

A bounded beam search is used instead of one-step greedy selection. This matters because two candidates can be weak individually yet complementary across private scenarios.

## 3. Championship risk planner

`championship_risk.py` composes the two ideas:

```text
existing exact replay/runtime hard gates
  -> censored replay-wall calibration
  -> risk-bounded candidate cap per model
  -> private scenario beam search
  -> robust private score
  -> multiply by probability the atomic phase completes
```

The final reported `atomic_adjusted_robust_raw_score` makes the catastrophic-loss probability visible instead of burying it in a runtime heuristic.

The JSON adapter and CLI expose the path as:

```bash
kaggle-security-lab championship-risk-run examples/championship-risk.example.json
```

## 4. Relationship to earlier winner-gap work

This is additive:

```text
timing signal
  -> estimate private-path survival from environment-bound evidence
minimum winning trace
  -> remove unnecessary steps
termination economics
  -> remove cost after success
runtime contract
  -> bound hosted execution assumptions
replay-wall risk
  -> avoid all-or-nothing candidate-count failure
private scenarios
  -> avoid correlated hidden-guardrail failure
```

## Boundary

This is controlled benchmark planning over recorded or caller-owned evidence. It does not generate operational attack payloads, does not infer secrets from live systems, and grants no BLACK authority. Public leaderboard score remains an observation channel, not the championship objective.
