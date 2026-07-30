# Reusable AI Agent Architecture

## Objective

Provide a domain-independent runtime for agents that must interact with external systems safely and measurably.

## Layers

### 1. Observation Adapter

Transforms external state into a stable internal schema.

Responsibilities:

- Preserve source identifiers and option ordering
- Distinguish public, private, and unavailable information
- Reject malformed or incomplete observations
- Produce deterministic state fingerprints

### 2. Candidate Compiler

Converts currently available external actions into typed candidates.

Responsibilities:

- Never invent unavailable actions
- Preserve action indexes and selection constraints
- Attach preconditions, expected effects, and risk metadata
- Separate optional from mandatory selections

### 3. Hierarchical Planner

Plans at multiple horizons rather than scoring every action with one flat function.

```text
Business Goal
    -> Workflow Plan
        -> Step Route
            -> Executable Action
```

This separation prevents a locally attractive action from silently breaking the longer objective.

### 4. Evaluator

Scores routes using explicit criteria:

- Goal progress
- Resource use
- Reversibility
- Failure risk
- Information quality
- Expected latency and cost
- Policy compliance

### 5. Policy Gate

Applies hard constraints before execution.

Examples:

- Human approval required
- Action forbidden without evidence
- External option no longer available
- Duplicate or cyclic operation detected
- Cost or latency budget exceeded

### 6. Executor

Executes exactly one validated action and records the result.

Required controls:

- Timeout
- Retry policy
- Idempotency key
- Safe fallback
- Structured error classification
- No silent exception swallowing

### 7. Audit and Telemetry

Every run should preserve:

```text
run_id
state fingerprint
goal
candidate actions
selected action
rejected actions and reasons
policy decisions
evidence references
external response
latency
cost
final status
```

### 8. Evaluation Harness

Policy changes are not promoted from intuition alone.

A promotion gate should include:

- Fixed scenario fixtures
- Contract tests for external APIs
- Regression tests for previously solved cases
- Error, timeout, and invalid-action counts
- Quality or task-success metrics
- Before/after comparison

## Domain adapters

The control plane should remain independent from each target system.

```text
control_plane/
  planner/
  evaluator/
  policy/
  runtime/
  telemetry/
  evaluation/

adapters/
  competition_engine/
  crm/
  email/
  rag/
  ticketing/
```

## FastAPI boundary

Suggested service boundaries:

```text
POST /runs                 create a run
GET  /runs/{id}            retrieve state
POST /runs/{id}/approve    resolve an approval gate
POST /runs/{id}/cancel     cancel execution
GET  /runs/{id}/trace      inspect decision evidence
POST /evaluations          execute scenario suites
GET  /metrics              operational metrics
```

## Next.js operations view

The dashboard should prioritize evidence over decorative chat output.

Recommended panels:

- Current goal and route
- Selected action
- Rejected candidates with reasons
- Policy-gate status
- Tool calls and external responses
- Latency, cost, success rate, and errors
- Evaluation results by policy version

## Reliability contract

A production-ready agent must satisfy these invariants:

1. It never executes an action absent from the current external contract.
2. It never treats unavailable information as observed fact.
3. It records why the chosen action beat its alternatives.
4. It fails closed when required evidence is missing.
5. It can replay and evaluate decisions from stored traces.
6. It separates experimental policies from promoted policies.
