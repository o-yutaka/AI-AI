# Kaggle Winning Strategy v1

This layer turns the strongest transferable competition lessons into reusable,
BLACK-independent research primitives. It deliberately avoids hard-coding one
attack family, one model, or one evaluator implementation.

## Research flow

```text
semantic genome warm start
  -> deterministic beam search
  -> proxy observation
  -> ridge proxy→target calibration
  -> runtime-sensitivity analysis
  -> exact target-runtime replay gate
  -> minimum winning trace reduction
  -> throughput / robustness measurement
  -> failure-correlation-aware portfolio selection
```

### Semantic genome + search

`SemanticGenome` represents instruction wording, clause order, protocol examples,
layout, and termination as explicit genes. The identity hash changes when gene
text, enablement, or order changes. `beam_search_semantic_genomes()` evaluates a
caller-owned mutation neighborhood with deterministic deduplication and tie
breaking, so semantic evolutionary warm starts are reproducible instead of
being hidden prompt edits.

### Ridge transfer calibration

`fit_ridge_transfer()` models systematic proxy→target drift while shrinking an
unstable slope. `residual_max` is retained so callers can rank candidates by a
conservative target-side lower bound instead of a raw proxy score.

### Runtime sensitivity

`analyze_runtime_sensitivity()` measures success-rate loss and score spread
across explicit `RuntimeVariant` identities. Runtime/compiler/quantization drift
is therefore a first-class research signal rather than noise folded into one
aggregate score.

### Exact target replay

`evaluate_target_replay()` requires exact `EnvironmentIdentity` equality and
also checks probe binding, trajectory evidence binding, required verdict,
required observable, and completion. A runtime/version change is therefore an
explicit failed gate rather than invisible noise.

### Minimum winning trace

`minimize_winning_trace()` searches prefixes in ascending length and returns the
shortest prefix that still satisfies the caller-owned evaluator. It intentionally
does not use binary search because success across multi-step traces is not
assumed to be monotonic.

### Failure correlation

`build_failure_correlation_graph()` measures pairwise Jaccard overlap over
ordered failure contexts. `select_correlation_diverse_portfolio()` then
penalizes candidates that fail in the same contexts as already selected
candidates, instead of relying only on a manually assigned cluster label.

## Boundary

These are research utilities only.

```text
Kaggle research gate != independent verification
Kaggle research gate != BLACK authority
Kaggle research gate != adoption / promotion / routing / execution
```

The only future BLACK-facing boundary remains `security-research-bundle.v1`.
