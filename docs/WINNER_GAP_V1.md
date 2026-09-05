# Winner-gap v1: timing evidence and termination economics

Post-close analysis of the first-place solution exposed two execution advantages that are orthogonal to ordinary prompt search:

1. a replay-latency signal can sometimes distinguish a successful path from a blocked path before the hidden guardrail is directly visible;
2. once the scored action has already happened, every unnecessary generated token or follow-up turn consumes replay budget without adding score.

A contemporaneous solution analysis summarizes the winner's method here:

`https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/writeups/optimizing-scored-harm-per-model-turn-in-multi-ste`

The winner's own solution is linked from that note as:

`https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/writeups/1st-place-solution`

This repository converts those ideas into benchmark-only research primitives without embedding any operational payload.

## 1. Timing signal

`timing_signal.py` calibrates only from labeled replay observations. It requires:

- one exact environment identity;
- explicit `SUCCESS` and `BLOCKED` labels;
- a minimum number of samples per class;
- configurable minimum timing separation.

The calibration learns whether success is faster or slower instead of assuming one direction. A robust scale is derived from within-class deviation and the median separation.

Unknown observations then produce a bounded success probability. `infer_timing_survival()` returns mean, median and a conservative lower-quartile-style probability.

### Fail-closed properties

- mixed environment identities are rejected;
- weakly separated timing classes are rejected;
- cross-environment inference is rejected;
- a finding cannot provide both a manual private-survival probability and timing-derived survival.

## 2. Championship integration

A `championship-run` JSON may define root-level `timing_calibrations`. A finding can then replace:

```json
{"private_survival_probability": 0.8}
```

with evidence-bound timing input:

```json
{
  "timing_signal": {
    "calibration_id": "private-path",
    "environment_key": "exact-runtime-key",
    "elapsed_seconds": [1.04, 1.08, 1.02]
  }
}
```

The conservative timing-derived probability enters the existing private objective. This keeps the chain explicit:

```text
labeled replay timing
  -> environment-bound calibration
  -> conservative survival estimate
  -> official-score expectation
  -> runtime-budgeted championship selection
```

## 3. Termination economics

`termination_economics.py` begins only after a scored action is already known to succeed. Each sample records:

- whether the successful action was preserved;
- post-success token count;
- post-success latency;
- runtime identity;
- optional end-of-generation margin.

The selector first gates on preserved success across runtimes. Only then does it minimize worst-case and mean post-success cost. An optional minimum EOG margin prevents a fragile cheap termination from outranking a stable one.

This complements `minimum_trace.py`:

```text
minimum winning trace
  -> remove unnecessary steps
termination economics
  -> remove unnecessary cost after success
runtime sensitivity
  -> require the saving to survive runtime changes
```

`post_success_capacity_gain()` translates a measured cost reduction into additional theoretical replay slots under a fixed benchmark budget. It is intentionally labeled as the gain from post-success cost alone, not as a full hosted-runtime prediction.

## 4. Why this is separated from payload generation

The research value is in measurement and resource allocation, not in hard-coding one benchmark string or one guardrail quirk. The modules therefore accept recorded timing, token, margin and runtime evidence and do not generate attack payloads.

This makes the primitives reusable for future agent-security benchmarks where the exact predicates, guardrails, models and parsers differ.
