# AI Agent Control Plane

[![CI](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml)

A working full-stack reference system for **contract-aware, auditable, human-approved AI agents**.

The project demonstrates the engineering around an AI model: which actions it is allowed to take, why one action was selected, which candidates were rejected, when human approval is mandatory, how duplicate side effects are prevented, and how the complete decision survives a process restart.

## Engineering proof

| Concern | Implemented evidence |
|---|---|
| API and validation | FastAPI + Pydantic request/response contracts |
| Allowed tool boundary | Versioned action contract and allow-list filtering |
| Authorization | Per-action permission requirements |
| High-impact safety | Evidence requirement plus named human approval/rejection |
| Deterministic decisions | Stable ranking, tie-breaking, and request fingerprints |
| Duplicate prevention | Idempotency key with conflicting-request detection |
| Auditability | Timestamped events, policy checks, rejected reasons, revisions |
| Failure handling | Structured executor error recorded in the trace |
| Restart safety | Pluggable repository with durable SQLite implementation |
| Full-stack operations | Next.js dashboard for run, review, approval, and trace inspection |
| Delivery | Docker Compose and GitHub Actions |

## Run the full stack

```bash
docker compose up --build
```

Open:

- Dashboard: `http://localhost:3000`
- FastAPI/OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Docker Compose configures `AGENT_DB_PATH=/data/control-plane.sqlite3` and a named volume. Completed runs, pending approvals, and idempotency records remain available after the API container restarts.

## Demo flow

1. Submit a low-risk support workflow and observe immediate execution.
2. Submit a high-risk refund workflow with supporting evidence.
3. Inspect the selected action, lower-ranked candidates, contract checks, and exact rejection reasons.
4. Approve or reject the pending action with an operator name and reason.
5. Restart the API container and retrieve the same trace.
6. Resubmit the same idempotent request and verify that the executor is not called twice.

## Architecture

```text
Next.js Operations Dashboard
             |
          FastAPI
             |
       Agent Runtime
  +----------+-----------+
  |          |           |
Contract  Candidate    Policy
 checks     ranking      gate
  |          |           |
  +------ selected action
             |
    approval / rejection
             |
          Executor
             |
  audit events + result/error
             |
      RunRepository
       /          \
  in-memory      SQLite
```

`AgentRuntime` owns decision policy, not persistence details. It depends on a small `RunRepository` protocol:

- `InMemoryRunRepository` keeps the embedded/test path simple.
- `SQLiteRunRepository` stores validated `DecisionTrace` JSON, indexes idempotency keys, uses WAL mode, and supports approval continuation after restart.

See [`docs/adr/0001-durable-run-store.md`](docs/adr/0001-durable-run-store.md) for the decision, guarantees, trade-offs, and non-goals.

## Agent runtime

- Versioned external action contract
- Action allow-list enforcement
- Per-action permission checks
- High-risk evidence requirement
- Deterministic ranking and tie-breaking
- High-risk and irreversible action approval gate
- Named approval or rejection with a reason
- Idempotency protection against duplicate execution
- Conflict detection when one idempotency key is reused for different input
- Structured executor-failure recording
- Observation and request fingerprints
- Timestamped audit events and revision tracking
- Defensive-copy repository reads
- Restart-safe SQLite persistence without an additional database package

## API

```text
GET  /health
POST /v1/runs
GET  /v1/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/decision
```

### Low-risk run

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  --data @examples/low-risk-run.json
```

### Approval-gated run

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  --data @examples/high-risk-run.json
```

### Approve

```bash
curl -X POST http://localhost:8000/v1/runs/<run_id>/decision \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approve",
    "approver": "ops@example.com",
    "reason": "Evidence and policy verified"
  }'
```

Use `"decision": "reject"` to reject. A rejected run never calls the executor.

## Operations dashboard

- Current run status and selected action
- Risk and reversibility
- Contract version and trace revision
- Eligible and rejected candidate counts
- Rejected actions with exact reasons
- Policy checks and details
- Human approval/rejection controls
- Audit-event timeline
- Result or structured error
- Observation and request fingerprints

## Local backend development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
uvicorn app:app --reload
```

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
pytest -q
uvicorn app:app --reload
```

Use SQLite outside Docker:

```bash
AGENT_DB_PATH=.data/control-plane.sqlite3 uvicorn app:app --reload
```

Without `AGENT_DB_PATH`, the app uses the in-memory repository.

## Local frontend development

```bash
cd web
npm install
npm run dev
```

The default API URL is `http://localhost:8000`. Override it at build time with `NEXT_PUBLIC_API_BASE_URL`.

## Repository structure

```text
.
├── app.py
├── control_plane/
│   ├── errors.py
│   ├── models.py
│   ├── runtime.py
│   └── store.py
├── tests/
│   ├── test_api.py
│   ├── test_persistence.py
│   └── test_runtime.py
├── web/
│   ├── app/
│   ├── Dockerfile
│   └── package.json
├── examples/
├── docs/
│   ├── adr/
│   ├── case-study-pokemon.md
│   └── evidence.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .github/workflows/ci.yml
```

## Verification gates

GitHub Actions verifies:

- Ruff
- pytest on Python 3.11 and 3.12
- Next.js production build on Node.js 22
- Backend Docker image build
- Frontend Docker image build

Persistence tests specifically verify:

- a completed idempotent run is not executed again after restart
- a pending high-risk action can be approved after restart
- listed/deserialized traces cannot mutate stored state

## Transfer from strict simulation agents

The architecture was extracted from a stateful competition agent connected to a strict external engine, then translated into a business workflow instead of publishing game-specific policy as the product.

| Strict-engine constraint | Business-agent equivalent | Public implementation |
|---|---|---|
| Select only engine-provided options | Call only currently allowed tools | Versioned action contract |
| Preserve option and workflow state | Preserve transaction state | Durable run trace |
| Do not assume hidden information | Do not treat unavailable data as fact | Caller observation + fingerprint |
| Resource-sensitive decisions | Permissions, cost, rate limits | Policy metadata and checks |
| Invalid action is unacceptable | Unauthorized or unsupported API call | Candidate filtering |
| Replay and policy comparison | Audit and regression evaluation | Decision events and tests |

Read [`docs/case-study-pokemon.md`](docs/case-study-pokemon.md) for the transfer boundary.

## Claim boundary

This is a portfolio-grade reference system, not a finished enterprise platform.

It demonstrates a durable single-node control plane, but it does **not** claim:

- production authentication or tenant isolation
- PostgreSQL or distributed database operation
- durable background queues
- real CRM, email, billing, or RAG connectors
- a live LLM planner/provider router
- load-test evidence or production SLOs
- multi-region replication or distributed transactions

See [`docs/evidence.md`](docs/evidence.md) for the distinction between public reproducible evidence and private source-project context.

## Next priorities

1. Authentication, RBAC, and tenant isolation
2. Async tool executor with timeout and retry policy
3. OpenAI-compatible planner/provider adapter
4. CRM, email, RAG, and billing adapters
5. Append-only audit/event storage
6. Evaluation fixtures and measured policy-promotion gates

## Author

Built by [o-yutaka](https://github.com/o-yutaka) as a public AI-agent engineering portfolio focused on reliable business automation.
