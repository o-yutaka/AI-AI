# Kaggle AI Agent Security Lab — Canonical Architecture

Status: canonical architecture for this repository.

Canonical project name: **Kaggle AI Agent Security Lab**  
Canonical repository slug: **`kaggle-ai-agent-security-lab`**  
Primary competition: **AI Agent Security - Multi-Step Tool Attacks** (`ai-agent-security-multi-step-tool-attacks`)

## Definition

This repository is an independent research and evaluation lab for multi-step AI-agent tool security.
It is not BLACK, does not depend on BLACK packages, and does not mint BLACK authority or BLACK learning records.

The existing `control_plane/` implementation is retained as the deterministic agent/tool evaluation runtime.
The new `research_bundle/` package is the only canonical knowledge-export boundary.

## Permanent boundaries

```text
KAGGLE LAB != BLACK
Research Finding != BLACK Lesson
Research Bundle != BLACK Experience
External Observation != Independent Verification
Benchmark Result != Adoption Authority
Benchmark Result != Execution Authority
```

The repository may emit facts, traces, hypotheses, benchmark results, transfer observations, failure modes, and provenance.
It may not declare that BLACK should adopt, promote, route, authorize, or execute anything.

## Architecture

```text
Competition / local benchmark inputs
              |
              v
       Hypothesis Engine
              |
              v
         Probe Compiler
              |
              v
      Candidate Generator
              |
              v
  +--------------------------+
  | existing control_plane/  |
  |                          |
  | contract gate            |
  | permission gate          |
  | evidence gate            |
  | sensitive-data gate      |
  | deterministic ranking    |
  | approval gate            |
  | ToolRegistryExecutor     |
  | fingerprint/idempotency  |
  +--------------------------+
              |
              v
        Trace / Replay
              |
              v
    Failure + Transfer Analysis
              |
              v
      Robustness Evaluation
              |
              v
     research_bundle/
 security-research-bundle.v1
              |
              v
 canonical JSON + SHA-256
              |
              v
        external consumer
```

## Canonical research objects

The export vocabulary is intentionally separate from BLACK's internal vocabulary:

- `Hypothesis`
- `Probe`
- `Observation`
- `Trajectory`
- `Finding`
- `FailureFinding`
- `RobustnessResult`
- `BenchmarkResult`
- `ProvenanceRecord`
- `SecurityResearchBundle`

Reserved BLACK concepts are not exported as authoritative objects:

- `Experience`
- `Lesson`
- `HeldOutLearningEvaluation`
- adoption/promotion decisions
- execution authority

## Research loop

```text
Hypothesis
  -> minimal falsification condition
  -> Probe
  -> Observable
  -> Evidence update
  -> family posterior/update
  -> eliminate unsupported families
  -> optimize surviving specialists
  -> robustness / transfer measurement
  -> canonical ResearchBundle
```

Public leaderboard or public guardrail behavior is treated as an observation channel, not ground truth for hidden evaluation.
Runtime duration and denial behavior may be recorded as observations, but never promoted to hidden-system facts without independent evidence.

## Evaluation discipline

Use explicit split identity for all experiments:

```text
TRAIN
DEV
HELD_OUT
ADVERSARIAL_HELD_OUT
```

A public score may guide hypothesis updates, but candidate selection should consider hidden-transfer risk, family correlation, replay completion, throughput, and robustness.

Preferred optimization target:

```text
Expected Hidden Utility
= Predicate Weight
  x Emission Probability
  x Guardrail Survival
  x Replay Completion
  x Candidate Throughput
```

The lab should prefer Minimum Winning Traces: the shortest reproducible trajectory that satisfies the measured predicate without unnecessary steps.

## BLACK compatibility boundary

The intended future flow is:

```text
Kaggle AI Agent Security Lab
  -> security-research-bundle.v1
  -> external adapter
  -> validated external artifact/evidence
  -> BLACK authoritative Mission binding
  -> BLACK creates its own Experience
  -> BLACK held-out evaluation
  -> BLACK Decision-gated adoption
```

BLACK is responsible for determining independence, truth status, held-out validity, promotion, adoption, and authority.
This repository remains a producer of research evidence only.

## Existing runtime reuse

`control_plane/` remains valuable and should not be rewritten merely for naming consistency. It already provides:

- untrusted candidate handling
- contract / permission / evidence gates
- sensitive-payload rejection
- declared tool capability enforcement
- deterministic ranking
- approval gating
- request fingerprints
- idempotency and replay
- fixed HTTP tool surfaces
- bounded responses and no redirects
- durable run/audit storage

Future Kaggle-specific modules should compose around this runtime instead of bypassing it.

## Next implementation layers

```text
src/evaluator
src/hypothesis
src/probes
src/replay
src/optimization
src/transfer
src/robustness
src/judge
src/research
```

These are implementation directions, not authority layers. `research_bundle/` remains the canonical external contract.
