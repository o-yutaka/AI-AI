# Portfolio Contract — AI-AI

## Positioning

AI-AI is the short-path business demonstration: a full-stack AI Agent control plane that shows how model output is kept untrusted until contract, permission, evidence, privacy, and tool-capability gates pass.

## Hiring evidence

- Python + FastAPI runtime
- OpenAI-compatible candidate planner
- Contract and permission enforcement
- Evidence and sensitive-data gates
- Deterministic ranking
- Human approval/rejection for high-impact actions
- Idempotency and conflict detection
- Durable SQLite state and audit events
- Next.js operations dashboard
- Browser proof with desktop/mobile evidence
- Docker Compose and GitHub Actions verification

## Business translation

```text
Customer request
  → Observation
  → Candidate actions
  → Contract / Permission / Evidence
  → Decision
  → Approval when required
  → Tool execution
  → Audit / Replay
```

The same runtime can be adapted to customer support, CRM, document processing, internal knowledge, sales operations, and approval workflows.

## Recruiter path

1. Open the public demo.
2. Read the proof table in `README.md`.
3. Run `docker compose up --build`.
4. Inspect `app.py`, `control_plane/`, `web/`, and `tests/`.
5. Review the claim boundary before inferring production scope.

## Claim boundary

The repository is a portfolio-grade single-node reference system. It does not claim enterprise RBAC, multi-tenant isolation, distributed queues, regulatory certification, or customer production traffic without separate evidence.
