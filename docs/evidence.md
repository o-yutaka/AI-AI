# Evidence and Claim Boundary

This repository separates **publicly reproducible evidence** from contextual claims about the private competition source project.

## Publicly reproducible here

### Backend

- FastAPI endpoints for creating, listing, reading, approving, and rejecting runs
- Contract allow-list enforcement
- Permission enforcement
- Evidence requirement for high-risk actions
- Deterministic ranking and tie-breaking
- Human approval and rejection records
- Idempotent run creation
- 409 conflict for idempotency-key reuse with different input
- Structured executor-failure traces
- Defensive-copy storage behavior
- CORS support for the local dashboard
- Unit and HTTP API tests

### Frontend

- Next.js App Router application written in TypeScript
- Low-risk and approval-gated workflow controls
- Approval and rejection actions
- Selected and rejected candidate inspection
- Policy-check inspection
- Audit timeline
- Result/error and trace-fingerprint display

### Delivery

- Python 3.11 and 3.12 CI jobs
- Next.js production-build CI job
- Backend and frontend Docker build jobs
- Docker Compose full-stack startup

Run:

```bash
docker compose up --build
```

Or verify components separately:

```bash
pip install -e ".[dev]"
ruff check .
pytest -q

cd web
npm install
npm run build
```

## Source-project context not published here

The original competition repository contains domain-specific official-engine adapters, policy code, match traces, search components, and submission assets. Those assets are intentionally not copied into this portfolio repository. This repository implements the transferable control-plane pattern; it is not a reproducible public copy of the entire competition system.

## Claims intentionally not made

This repository does not claim to provide:

- Production-ready persistence
- Authentication, RBAC, or multi-tenant isolation
- A live LLM provider router
- Real CRM, email, RAG, payment, or ticketing integrations
- Distributed workers or durable queues
- Production-grade network retry and timeout handling
- Load-test evidence, SLOs, or security certification

Those remain roadmap items until corresponding code and evidence are committed.
