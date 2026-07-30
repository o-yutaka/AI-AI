# Reusable AI Agent Architecture

## Implemented full-stack boundary

```text
Next.js dashboard
    -> FastAPI request
    -> typed RunRequest
    -> current action contract
    -> candidate eligibility checks
    -> deterministic ranking
    -> policy gate
    -> approval or rejection
    -> executor
    -> stored trace copy
    -> dashboard inspection
```

The implementation is intentionally small and uses in-memory storage. It demonstrates control flow and invariants, not production persistence.

## Implemented invariants

1. Candidate IDs must be unique.
2. An action outside the current contract cannot execute.
3. Required permissions must be granted.
4. High-risk actions require evidence.
5. High-risk or irreversible actions require a named human decision.
6. A rejected action is never executed.
7. Repeating the same request with the same idempotency key does not execute twice.
8. Reusing an idempotency key for different input is rejected.
9. Executor exceptions become structured failed traces.
10. Retrieval returns a defensive copy rather than the stored object.
11. Set ordering cannot change request fingerprints.
12. Candidate tie-breaking is deterministic.

## Components

### Action contract

The contract carries a version, currently allowed action IDs, and granted permissions. This maps to an external engine option list, a SaaS capability document, or a user authorization scope.

### Candidate validation

Candidates are rejected before ranking when they are absent from the current contract, require missing permissions, or lack evidence required by risk policy.

### Deterministic ranking

Eligible candidates are sorted by:

1. Higher expected value
2. Lower risk
3. Reversible before irreversible
4. Lexicographically smaller action ID

### Approval gate

High-risk or irreversible selected actions enter `waiting_approval`. A named approver submits `approve` or `reject` with a reason. Rejected runs never call the executor.

### Audit trace

Each trace records:

- Observation fingerprint
- Request fingerprint
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

### Operations dashboard

The Next.js client exposes the runtime behavior directly rather than presenting a decorative chat screen. It shows decisions, rejected alternatives, policy checks, approval state, execution events, and trace identity.

## Production extension points

- PostgreSQL run repository and append-only event store
- Authentication, RBAC, and tenant isolation
- Durable queue and worker processes
- Timeout and retry policies around network tools
- OpenAI-compatible model/planner routing
- OpenTelemetry metrics and traces
- Real CRM, email, RAG, and billing adapters
