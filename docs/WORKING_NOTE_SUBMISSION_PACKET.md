# Working Note Award — Submission Packet

This packet turns the repository's current research record into a submission-ready Working Note without claiming that post-deadline engineering changed the September 1 leaderboard result.

## Deadline

Kaggle lists the optional Working Note deadline as **September 8, 2026 at 11:59 PM UTC**. In Japan that is **September 9, 2026 at 08:59 JST**.

Official competition page:

`https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/overview/prizes`

## Recommended title

**Selection Under Hidden Guardrails: Evidence-First Search, Runtime Identity, and Private-Transfer Measurement for Multi-Step Agent Security**

## Recommended source document

Start from:

`docs/WORKING_NOTE_AWARD_DRAFT.md`

Then include the winner-gap material from:

`docs/WINNER_GAP_V1.md`

The final note should remain one coherent story rather than two pasted documents.

## One-sentence contribution

Treat public leaderboard feedback as a sensor rather than the objective, eliminate weak mechanism families before expensive search, bind findings to exact execution identity, preserve negative evidence, and select candidates by conservative expected private replay value per unit runtime.

## What is strongest and should be foregrounded

### 1. Methodological contribution

The repository is not a prompt list. It is an evidence-first research harness:

```text
hypothesis
  -> bounded falsification
  -> semantic / optimizer search
  -> proxy-to-target calibration
  -> exact replay gate
  -> runtime + nuisance sensitivity
  -> minimum winning trace
  -> private-survival estimate
  -> diversity-aware, runtime-budgeted selection
```

Key code:

- `security_lab/research_loop.py`
- `security_lab/semantic_search.py`
- `security_lab/transfer.py`
- `security_lab/target_gate.py`
- `security_lab/runtime_sensitivity.py`
- `security_lab/nuisance.py`
- `security_lab/minimum_trace.py`
- `security_lab/competition_objective.py`
- `security_lab/championship.py`

### 2. Hidden-guardrail transfer as a measurable quantity

The note should explicitly distinguish three levels:

1. public/proxy observation;
2. evidence-derived private-survival estimate;
3. actual private result, when available.

The final selector does not use public rank as its objective. It models expected replay value from severity, cell diversity, survival probability, and runtime cost.

For duplicate cells:

```text
P(cell survives) = 1 - product(1 - p_i)
```

This avoids pretending that correlated duplicates add independent diversity.

### 3. Runtime identity is security evidence

A replay result is bound to model/runtime/compiler/tokenizer/quantization/tool-surface/evaluator identity. Unknown compiler bindings do not fall back silently.

Key code:

- `security_lab/sdk_runtime_contract.py`
- `security_lab/compiler_registry.py`
- `security_lab/models.py`
- `security_lab/target_gate.py`

This is a useful benchmark-design lesson independent of leaderboard rank: if a security finding disappears after parser, tokenizer, quantization, or runtime drift, that dependency is part of the finding.

### 4. Negative results are retained

The v2 neutral research bundle keeps rejected paths, blocked/inconclusive probes, failure modes, runtime sensitivity, transfer behavior, nuisance effects, environment identities, and budget decisions.

Key code:

- `research_bundle/models.py`
- `security_lab/export_bridge.py`
- `security_lab/research_roles.py`

This supports a strong security insight: failed mechanisms narrow the future search space and should be reproducible artifacts, not discarded leaderboard history.

## Post-close first-place analysis: how to present it honestly

The first-place writeup became available after the final submission deadline. Do **not** imply that the later timing/termination modules powered a September 1 competition submission.

Recommended framing:

> After the final submission deadline, the first-place solution exposed two execution-level ideas that stress-tested our architecture: private-path information could be inferred from calibrated replay timing, and post-success generation cost could dominate throughput. We implemented both as environment-bound measurement primitives and integrated the timing estimate into the same private-objective selector. These are post-close replications/extensions, not claims about our submitted leaderboard artifact.

Relevant code:

- `security_lab/timing_signal.py`
- `security_lab/timing_signal_io.py`
- `security_lab/termination_economics.py`
- `tests/test_winner_gap_signals.py`
- `tests/test_championship_timing_signal.py`

The useful generalization is stronger than copying a single competition trick:

- timing direction is learned from labeled samples rather than assumed;
- calibration cannot mix environment identities;
- weak separation fails closed;
- cross-environment inference fails closed;
- timing-derived survival and manually supplied survival cannot both control one finding;
- termination optimization happens only after successful action preservation is proven across the required runtimes.

## Reproducibility section — concrete commands

Use the repository's actual public interfaces:

```bash
kaggle-security-lab research-run <research-spec.json>
kaggle-security-lab rank-winning-portfolio <evidence-spec.json>
kaggle-security-lab championship-run <championship-spec.json>
```

Useful example:

```bash
kaggle-security-lab championship-run examples/championship-strategy.example.json
```

Remote benchmark execution is separate and explicit:

```text
kaggle-stage
kaggle-run
kaggle-status
kaggle-output
kaggle-submit
```

The note should explain that remote outputs are research artifacts and are not silently promoted into claims.

## Award-criteria mapping

Kaggle's five criteria can be answered directly:

| Kaggle criterion | Evidence in this repository |
| --- | --- |
| Technical clarity & reproducibility | deterministic search, frozen identities, canonical hashes, one-command interfaces, Python 3.11/3.12 CI |
| Methodological contribution | hypothesis-first elimination, conservative transfer calibration, private-objective selection, exact runtime contracts |
| Security insight | public/private family transfer, environment identity as evidence, negative-result preservation |
| Benchmark usefulness | reusable schemas, optimizer SPI, compiler registry, timing/runtime/nuisance measurement primitives |
| Responsible communication | controlled offline benchmark scope; no live-system exploitation instructions |

## Evidence checklist before publishing

Do not publish an empirical number unless the exact artifact or run that supports it is available.

Safe claims already supported by repository structure/tests:

- public/proxy score is absent from the final championship objective;
- severity weights and unique-cell expectation are modeled explicitly;
- runtime budgets are versioned inputs rather than hidden constants;
- exact compiler compatibility has no implicit fallback;
- timing calibration rejects mixed environments;
- timing direction is learned rather than assumed;
- post-success termination ranking gates on preserved success first;
- research exports grant no deployment or BLACK authority.

Claims requiring named run evidence before publication:

- any specific leaderboard improvement attributable to this repository;
- any specific private-survival percentage measured on Kaggle;
- any throughput speedup on the hosted evaluator;
- any claim that post-close code changed the submitted competition result;
- any claim of reproducing the winner's exact private score.

## Suggested final structure

1. Abstract
2. The central selection problem: public observation != private objective
3. Hypothesis-first family elimination
4. Semantic search and explicit lineage
5. Proxy-to-target calibration
6. Exact runtime/compiler identity
7. Runtime-contract drift and reproducibility
8. Runtime/nuisance sensitivity and minimum trace
9. Private-objective portfolio selection
10. Preserve failures and rejected paths
11. Post-close replication: environment-bound timing signal
12. Post-close replication: termination economics
13. Security lessons for future benchmarks
14. Limitations and evidence boundaries
15. Reproducibility commands/code map
16. Responsible communication

## Final editorial rules

- Prefer measured or code-verifiable statements over adjectives.
- Separate competition-period evidence from post-close engineering.
- Do not imply access to the hidden guardrail beyond observations actually obtained.
- Explain one surprising failure clearly; negative evidence is valuable to this award.
- Keep formulas small and tie every formula to the implementation.
- Link directly to reproducible files rather than only the repository root.
- End on benchmark-design lessons, not on an attack recipe.

## Submission state

The repository side can be made submission-ready here, but publishing the Working Note on Kaggle is a separate account action. No repository commit should be described as a Kaggle Working Note submission unless the Kaggle page itself confirms publication.
