# Kaggle AI Agent Security Lab — Operations

This document is the canonical operator path for the independent Kaggle research lab.

## 1. Freeze the research plan

Start from a versioned JSON specification and create a deterministic plan identity:

```bash
kaggle-security-lab plan-research examples/kaggle-research-plan.example.json
```

The output binds:

- competition/evaluator identity
- dataset source revision
- deterministic TRAIN/DEV/HELD_OUT/ADVERSARIAL_HELD_OUT assignment
- research budget allocation
- model/runtime/compiler/quantization matrix

The same inputs produce the same `plan_id` and SHA-256.

## 2. Freeze data independently

```bash
kaggle-security-lab freeze-dataset examples/kaggle-research-plan.example.json
```

For dedicated dataset-freeze input, provide `dataset_id`, `source_revision`, and `instance_ids`.
Do not silently reshuffle instances after observing results.

## 3. Allocate budget

```bash
kaggle-security-lab plan-budget 100
```

Default allocation:

```text
25% evaluator identification
25% falsification
35% optimization of surviving families
15% portfolio validation
```

This is a research default, not a leaderboard truth claim.

## 4. Select compute

```bash
kaggle-security-lab select-compute compute.json
```

The selector filters unavailable targets, insufficient VRAM, and insufficient remaining time before deterministic priority ordering.

## 5. Run research cases

The Python API uses:

```text
ExperimentCase
  -> compile_probe
  -> replay_probe
  -> Observation + Trajectory
```

Every replay is bound to `EnvironmentIdentity` so model/runtime/quantization/tool/evaluator context can be compared without confusing proxy success with target transfer.

## 6. Freeze candidate set

Use `freeze_candidates()` during discovery/validation and `package_candidates()` for the final immutable candidate metadata package.

```bash
kaggle-security-lab package-candidates candidates.json
```

Candidate package identity is order-independent and SHA-256 bound.

## 7. Export research evidence

Engine outputs are converted through `security_lab.export_bridge` into:

```text
security-research-bundle.v1
```

Then verify it:

```bash
kaggle-security-lab verify-bundle exports/security-research-bundle.json
```

The lab exports research observations. It does not mint BLACK Experience, BLACK Lesson, independent held-out truth, adoption, promotion, routing, or execution authority.

## Permanent flow

```text
ResearchPlan
  -> EvaluatorDecomposer
  -> HypothesisGraph
  -> ProbeCompiler
  -> ReplayHarness
  -> Belief update / Family elimination
  -> Runtime/transfer/robustness analysis
  -> Held-out research judge
  -> failure-diverse portfolio
  -> security-research-bundle.v1
  -> optional BLACK-side adapter later
```
