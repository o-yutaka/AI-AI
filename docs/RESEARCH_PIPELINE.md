# Kaggle AI Agent Security Lab — Research Pipeline

This repository is an independent Kaggle research system. It does not depend on BLACK and does not mint BLACK Experience, BLACK Lesson, held-out authority, adoption authority, promotion authority, routing authority, or execution authority.

## Pipeline

```text
EvaluatorSpec
  -> Evaluator Decomposer
  -> HypothesisGraph
  -> minimal falsification ProbeCompiler
  -> ReplayHarness
  -> Observation + Trajectory
  -> Family scoring / elimination
  -> proxy-to-target TransferCalibrator
  -> RobustnessEnvelope
  -> held-out Research Judge
  -> security-research-bundle.v1
```

## Split discipline

- TRAIN: discovery and candidate generation
- DEV: falsification and iteration
- HELD_OUT: frozen research evaluation
- ADVERSARIAL_HELD_OUT: frozen stress evaluation

A DEV result cannot receive `VERIFIED_FOR_RESEARCH`. Passing the research judge is still not BLACK verification or adoption authority.

## Existing control plane

`control_plane/` remains the deterministic action/tool runtime. The new `security_lab/` package owns evaluator identification, probe compilation, replay analysis, transfer calibration, robustness aggregation, and research judging.

The runtime boundary is intentional:

```text
security_lab decides what to measure
control_plane provides a governed deterministic environment
research_bundle records what was observed
```

## Future BLACK import

BLACK compatibility is data-only:

```text
security-research-bundle.v1
  -> BLACK-side adapter
  -> external artifact/evidence validation
  -> authoritative Mission binding
  -> BLACK creates its own Experience
```

No module in this repository imports BLACK packages or writes BLACK state.
