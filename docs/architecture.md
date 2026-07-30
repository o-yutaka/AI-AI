# Reusable AI Agent Architecture

## Implemented boundary

```text
FastAPI request
    -> typed RunRequest
    -> current action contract
    -> candidate eligibility checks
    -> deterministic ranking
    -> policy gate
    -> approval or rejection
    -> executor
    -> immutable-style stored trace copy
```

The current reference implementation is intentionally small and in-memory. It demonstrates control flow and invariants, not production persistence.

## Implemented invariants

1. Candidate IDs must be unique.
2. An action outside the current contract cannot execute.
3. Required permissions must be granted.
4. High-risk actions require evidence.
5. High-risk or irreversible actions require a named human decision.
6. A rejected action is never executed.
7. An idempotency key cannot execute the same request twice.
8. Executor exceptions become structured failed traces.
9. Retrieval returns a defensive copy rather than the stored object.
10. Candidate tie-breaking is deterministic.

## Components

### Action contract

The contract carries a version, the currently allowed action IDs, and granted permissions. This maps to an external engine option list, a SaaS API capability document, or a user's authorization scope.

### Candidate validation

Candidates are rejected before ranking when they are not in the current contract, require missing permissions, or lack evidence required by risk policy.

### Deterministic ranking

Eligible candidates are sorted by:

1. Higher expected value
2. Lower risk
3. Reversible before irreversible
4. Lexicographically smaller action ID

The tie-break rules are explicit and regression-tested.

### Approval gate

High-risk or irreversible selected actions enter `waiting_approval`. A named approver must submit either `approve` or `reject` with a reason. Rejected runs never call the executor.

### Audit trace

Each trace records:

- Observation fingerprint
- Contract version
- All candidates
- Eligible action IDs
- Rejected candidates and reasons
- Policy checks
- Selected action
- Approval identity and reason
- Execution result or structured error
- Timestamped events
- Revision number

## Production extension points

The following are deliberately outside the current implementation:

- PostgreSQL event and run repositories
- Authentication, RBAC, and tenant isolation
- Durable job queue and workers
- Timeout and retry policies around network tools
- OpenAI-compatible model routing
- Next.js operations dashboard
- OpenTelemetry metrics and traces
- Real CRM, email, RAG, and billing adapters

The interfaces should be extended without weakening the implemented invariants.
