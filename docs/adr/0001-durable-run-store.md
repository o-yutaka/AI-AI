# ADR 0001: Pluggable run repository with SQLite durability

## Status

Accepted for v0.3.0.

## Context

The original reference runtime stored every `DecisionTrace` and idempotency key in process memory. That made the policy engine easy to understand, but it also meant that a process restart lost pending approvals, completed-run history, and duplicate-execution protection.

The portfolio needs to demonstrate a production-relevant boundary without pretending to be a complete distributed platform.

## Decision

`AgentRuntime` depends on a small `RunRepository` protocol instead of owning dictionaries directly.

Two implementations are provided:

- `InMemoryRunRepository` remains the default for tests and embedding.
- `SQLiteRunRepository` persists the complete validated `DecisionTrace` JSON, indexes idempotency keys, and supports restart-safe lookup and approval continuation.

The FastAPI application selects SQLite only when `AGENT_DB_PATH` is set. Docker Compose sets that variable and mounts a named volume, so the default full-stack demo survives container restarts.

## Guarantees

- A repeated idempotent request after restart returns the original run and does not execute the tool again.
- A run waiting for approval can be approved or rejected by a later runtime process.
- Repository reads deserialize into fresh Pydantic models, so caller mutation cannot change stored state.
- No third-party database dependency is added; the implementation uses Python's standard `sqlite3` module.

## Non-goals

- Multi-region replication
- Distributed transactions
- Durable background queues
- Database-level event sourcing
- Authentication or tenant isolation

Those remain explicit future work rather than implied capabilities.

## Consequences

The runtime gains a real persistence seam and restart-safe behavior while preserving the simple in-memory path. SQLite serializes writes inside the repository with a lock and uses WAL mode, but it is still a single-node reference implementation.
