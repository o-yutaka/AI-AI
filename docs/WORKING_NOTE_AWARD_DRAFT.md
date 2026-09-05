# Selection Under Hidden Guardrails: An Evidence-First Research System for Multi-Step Agent Security

## Abstract

The hardest part of the AI Agent Security — Multi-Step Tool Attacks benchmark was not generating one high-scoring prompt. It was deciding which observed behaviors were real, which were artifacts of a public guardrail or runtime, and which candidates deserved scarce replay time under an unseen private guardrail.

We built the research process around that distinction. The system treats public feedback as an observation channel rather than the objective, eliminates weak attack families before expensive optimization, calibrates proxy-to-target drift, binds every replay to an exact model/runtime/compiler identity, reduces successful traces, measures nuisance and runtime sensitivity, and selects a portfolio by expected private replay value under a model-specific runtime budget. Negative results, rejected candidates, and environment identities are retained as first-class research material instead of being discarded.

The result is less a prompt collection than a reproducible research harness for hidden-guardrail selection. This note focuses only on the competition's deterministic offline sandbox and on lessons useful for safer agent evaluation.

## 1. Benchmark setting and the central mistake

The benchmark asks an attack algorithm to search for replayable multi-step failures in a controlled fixture-backed environment. The final standing is determined by private evaluation, while the public surface provides only partial feedback. The official evaluator also rewards both finding severity and diversity across tool-call cells.

That creates a selection problem:

```text
observable public behavior != hidden private objective
```

A candidate can be excellent on the visible guardrail and still be a poor final choice if its mechanism is tightly coupled to that guardrail. Conversely, a less spectacular public candidate can be valuable if it transfers across guardrails, runtimes, or nuisance conditions.

Our canonical research order became:

```text
identify evaluator behavior
  -> falsify attack families cheaply
  -> optimize surviving families
  -> calibrate proxy-to-target drift
  -> verify exact-runtime replay
  -> reduce unnecessary trace length
  -> measure runtime/nuisance stability
  -> estimate private survival
  -> select a diverse portfolio under runtime budget
```

The public score is intentionally absent from the final championship selector.

## 2. Hypothesis-first family elimination

We represent research ideas as explicit hypotheses with:

- a family identity;
- a falsification condition;
- an expected observable;
- a prior belief;
- bounded-cost probes.

Probe selection uses uncertainty per budget cost. Observations update posterior belief but do not become authority: `SUPPORTED`, `REFUTED`, `INCONCLUSIVE`, and `BLOCKED` remain distinct evidence states.

This matters because expensive semantic or evolutionary search is wasteful when the underlying family is wrong. The system therefore spends early budget on eliminating families, not polishing every candidate equally.

A bounded research loop enforces split leakage guards and a stage-specific budget ledger. When a probe cannot fit the remaining budget, the system records the rejected path and stops rather than silently overspending.

## 3. Search candidates are genomes, not hidden edits

For surviving families, prompt and protocol variations are represented as a `SemanticGenome` rather than ad-hoc string edits. Gene slots include instruction wording, clause structure, protocol examples, layout, and termination behavior.

The search layer provides deterministic beam search and a proposal-only optimizer interface. Candidate identity is content-derived, mutations preserve lineage, and duplicate variants are removed reproducibly.

The optimizer is deliberately proposal-only. Evaluation remains a separate boundary so a search strategy cannot manufacture its own evidence.

## 4. Transfer calibration and conservative ranking

A public or local proxy is useful only if its relationship to the target is measured. We fit a regularized one-feature transfer model from paired proxy/target observations:

```text
target ~= intercept + slope * proxy
```

The residual envelope is retained. Candidate ranking uses a conservative target estimate rather than the proxy score alone.

This converts "the proxy looks good" into a falsifiable statement about measured transfer. When the calibration is weak, the conservative estimate falls accordingly.

## 5. Exact runtime identity is part of the result

Agent behavior changed with runtime, model packaging, compiler behavior, tokenizer details, quantization, tool parsing, and evaluator revisions. We therefore treat environment identity as evidence, not metadata.

A target replay gate binds:

- model ID and revision;
- runtime ID and version;
- compiler ID;
- tokenizer revision;
- quantization;
- tool-surface hash;
- evaluator hash;
- probe/trajectory/observable/verdict/completion evidence.

A mismatch fails the gate instead of being folded into noise.

The compiler registry also has no implicit fallback. A compiler must be explicitly bound to an exact `(model, runtime, compiler)` compatibility identity. This prevents a generic formatting path from silently being reused after a target-specific parsing change.

## 6. Runtime contract drift is versioned evidence

The competition documentation changed during the event. A host FAQ clarified 9,000 seconds per model per evaluation phase, a 15-hour global runtime, 2,000 candidates, 32 user messages per candidate, and 8 tool hops per interaction. Other competition pages and SDK observations showed conflicting values for some runtime and method-signature details.

Rather than choosing one number and forgetting the disagreement, the system stores evaluator assumptions in a `CompetitionRuntimeContract` with a source reference, evidence tier, and canonical SHA-256 fingerprint.

Unknown values stay unknown. A host-sourced contract does not inherit an SDK-specific message-length limit unless that SDK observation is explicitly supplied. Changing any contract field changes the contract fingerprint.

Runtime planning reserves configurable headroom and calculates a safe candidate capacity from measured seconds per candidate. This makes timeout risk visible before portfolio construction.

Primary benchmark references:

- Host evaluator FAQ: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/discussion/712642
- SDK discrepancy discussion: https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/discussion/733119

## 7. Minimum winning trace

When a candidate succeeds, we search prefixes in ascending length and keep the shortest prefix that still satisfies the evaluator. We do not use binary search because success across a multi-step trajectory is not assumed to be monotonic.

Trace reduction has two benefits:

1. fewer unnecessary steps mean lower replay cost and fewer failure opportunities;
2. the resulting evidence is easier to interpret because the causal path is shorter.

This is a research reduction step, not an assumption that shorter is always semantically safer.

## 8. Runtime and nuisance sensitivity

A single successful replay is not treated as stable evidence.

Runtime sensitivity measures success-rate loss and score spread across explicit runtime variants. Nuisance analysis aggregates candidate outcomes across controlled nuisance conditions and can reject candidates whose apparent success is dominated by one fragile condition.

These measurements separate mechanism strength from incidental evaluator state.

## 9. Failure correlation and portfolio diversity

Selecting the individually best candidates can produce a portfolio whose members all fail in the same hidden condition. We therefore build failure profiles and calculate pairwise overlap. Portfolio selection penalizes candidates whose failure sets are strongly correlated with already selected candidates.

This is different from merely assigning candidates to hand-written families. Correlation is measured from observed failure contexts.

## 10. Private-objective selection

The final selector approximates the competition's replayed objective rather than public rank.

For each replay-successful finding we retain:

- predicate;
- severity;
- tool-call cell identity;
- measured runtime cost;
- an explicit private-survival probability derived from research evidence.

Expected severity contribution uses the competition severity weight multiplied by private-survival probability.

For multiple findings occupying the same cell, expected unique-cell value is:

```text
P(cell survives) = 1 - product(1 - p_i)
```

This avoids double-counting duplicate cells while preserving the benchmark's diversity incentive.

Within each target model's replay budget, the selector greedily chooses the largest marginal expected private-score gain per runtime second. Only candidates that already passed the exact replay/runtime hard gates are eligible.

The private-survival probability is not presented as ground truth. It is an explicit research estimate that can be calibrated, stress-tested, or replaced. Making this uncertainty visible is preferable to silently equating public success with private success.

## 11. Preserve what failed

A research system that stores only winners becomes systematically overconfident.

The export format therefore retains neutral `KnowledgeMaterial` and `ResearchDecisionRecord` objects for:

- supported and refuted hypotheses;
- blocked or inconclusive probes;
- runtime sensitivity;
- transfer behavior;
- robustness signals;
- semantic genomes;
- nuisance effects;
- failure correlation;
- eliminated candidates;
- trace reduction;
- throughput signals;
- evaluator observations;
- selected and rejected search paths;
- budget spent;
- exact environment identities.

These records carry `authority = NONE` and `independently_verified = false` where applicable. They are research material, not a claim that an external result should be deployed.

## 12. Reproducibility

The repository exposes deterministic components and one-command interfaces:

```bash
kaggle-security-lab research-run <research-spec.json>
kaggle-security-lab rank-winning-portfolio <evidence-spec.json>
kaggle-security-lab championship-run <championship-spec.json>
```

Remote experiments can be staged and executed through Kaggle notebooks, while outputs are downloaded as artifacts rather than being silently promoted.

Reproducibility controls include:

- frozen dataset identity and split leakage guards;
- canonical JSON and SHA-256 artifact identity;
- explicit environment/runtime/compiler identity;
- deterministic search tie-breaking;
- append-only research decisions and rejected paths;
- exact target replay gates;
- versioned runtime contracts;
- CI across Python 3.11 and 3.12;
- Ruff, tests, package/CLI smoke checks, lockfile verification, and proof artifacts.

Repository: https://github.com/o-yutaka/AI-AI

## 13. Security insight

Three benchmark-design lessons emerged from the system architecture.

### 13.1 A leaderboard is a sensor, not the objective

When the visible and hidden guardrails differ, optimizing the visible score can select the wrong failure family. Evaluation should make transfer uncertainty measurable rather than encouraging one-guardrail specialization.

### 13.2 Environment identity belongs in security evidence

If a finding depends on one runtime, parser, tokenizer, or quantization, that dependency is part of the finding. Reproducible agent-security benchmarks should bind findings to exact execution identity and report sensitivity across relevant variants.

### 13.3 Negative results are reusable security knowledge

A refuted family, a blocked path, or a runtime-specific failure narrows the search space for future evaluators. Benchmarks become more useful when those negative results are represented as structured artifacts rather than disappearing after a leaderboard iteration.

## 14. Limitations

This system does not know the hidden private guardrail. Its private-survival model is an estimate, not privileged access.

The current exact compiler registry prevents accidental cross-model fallback but does not claim that every model-specific prompt/tool formatter has been reverse-engineered. Compatibility should be added only from reproducible target evidence.

Likewise, a runtime contract records what a source establishes at a point in time; later evaluator updates require a new contract identity rather than retroactively changing old evidence.

Finally, components engineered after the final submission deadline are not represented here as having improved a submitted leaderboard artifact unless a named competition result proves that claim. The research repository keeps post-close engineering distinguishable from competition-period evidence.

## 15. Responsible communication

Everything described here is confined to the sanctioned deterministic offline benchmark. The repository focuses on search architecture, replay, evaluation, evidence identity, transfer measurement, and defensive benchmark design. It does not provide instructions for compromising deployed systems, stealing credentials, or exploiting unrelated services.

The intended transferable outcome is a better way to measure and defend tool-using agents: bind claims to evidence, treat hidden-guardrail transfer as uncertainty, preserve negative results, and require reproducible runtime identity before trusting a security finding.

## 16. Code map

Key modules:

- `security_lab/research_loop.py` — bounded hypothesis/probe loop
- `security_lab/semantic_genome.py` and `semantic_search.py` — reproducible candidate search
- `security_lab/transfer.py` — proxy-to-target calibration
- `security_lab/target_gate.py` — exact target replay gate
- `security_lab/minimum_trace.py` — shortest successful prefix search
- `security_lab/runtime_sensitivity.py` — runtime stability
- `security_lab/nuisance.py` — nuisance aggregation/screening
- `security_lab/failure_correlation.py` — correlated-failure portfolio control
- `security_lab/competition_objective.py` — private replay objective approximation
- `security_lab/championship.py` — hard-gated final selection
- `security_lab/sdk_runtime_contract.py` — versioned evaluator/SDK contract
- `security_lab/compiler_registry.py` — exact compiler compatibility binding
- `security_lab/export_bridge.py` and `research_bundle/` — neutral, lossless research export

The design goal is simple: search aggressively, but make every claim harder to fool than the search itself.
