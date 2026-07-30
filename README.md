# AI Agent Control Plane

[![CI](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml)

A working full-stack portfolio for **contract-aware, auditable, human-approved AI agents**.

- **Backend:** Python, FastAPI, Pydantic
- **Frontend:** TypeScript, Next.js App Router, React
- **Operations:** pytest, Ruff, Docker Compose, GitHub Actions

The architecture is extracted from a stateful competition agent connected to a strict external simulation engine. The public demo translates the same engineering constraints into a customer-support workflow: the agent may execute only currently allowed actions, must respect permissions, requires evidence and human approval for high-impact operations, prevents duplicate side effects, and preserves a complete decision trace.

## Run the full stack

```bash
docker compose up --build
```

Open:

- Dashboard: `http://localhost:3000`
- FastAPI/OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

The dashboard can run:

1. A low-risk support workflow that executes immediately
2. A high-risk refund workflow that pauses for approval
3. Approve or reject the pending action
4. Inspect selected and rejected actions, policy checks, audit events, result/error, and trace fingerprints

## What is implemented

### Agent runtime

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
- Defensive-copy in-memory storage

### API

```text
GET  /health
POST /v1/runs
GET  /v1/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/decision
```

### Operations dashboard

- Current status and selected action
- Risk and reversibility
- Contract version and trace revision
- Eligible and rejected candidate counts
- Rejected actions with exact reasons
- Policy checks and details
- Human approval/rejection controls
- Audit-event timeline
- Result or structured error
- Observation and request fingerprints

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
```

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

## Local frontend development

```bash
cd web
npm install
npm run dev
```

The default API URL is `http://localhost:8000`. Override it at build time with `NEXT_PUBLIC_API_BASE_URL`.

## API examples

Low risk:

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  --data @examples/low-risk-run.json
```

Approval gated:

```bash
curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  --data @examples/high-risk-run.json
```

Approve:

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

## Why the Pokémon competition work is relevant

| Competition-agent constraint | Business-agent equivalent | Public implementation |
|---|---|---|
| Select only engine-provided options | Call only currently allowed APIs/tools | Versioned action contract |
| Preserve option and workflow state | Preserve transaction state | Stateful run trace |
| Do not assume hidden information | Do not treat unavailable data as fact | Caller observation + fingerprint |
| Resource-sensitive decisions | Cost, inventory, permissions, rate limits | Policy metadata and checks |
| Invalid action is unacceptable | Unauthorized or unsupported API call | Candidate filtering |
| Replay and policy comparison | Audit and regression evaluation | Decision events and tests |

Read [docs/case-study-pokemon.md](docs/case-study-pokemon.md) for the detailed transfer boundary.

## Repository structure

```text
.
├── app.py
├── control_plane/
│   ├── errors.py
│   ├── models.py
│   └── runtime.py
├── tests/
│   ├── test_api.py
│   └── test_runtime.py
├── web/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── tsconfig.json
├── examples/
├── docs/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .github/workflows/ci.yml
```

## CI gates

GitHub Actions verifies:

- Ruff
- pytest on Python 3.11 and 3.12
- Next.js production build on Node.js 22
- Backend Docker image build
- Frontend Docker image build

## Claim boundary

This is a portfolio-grade reference system, not a finished enterprise platform. It currently uses in-memory storage and a deterministic example executor. It does **not** claim production authentication, tenant isolation, PostgreSQL persistence, durable queues, real SaaS connectors, a live LLM provider router, load-test evidence, or production SLOs.

See [docs/evidence.md](docs/evidence.md) for the exact distinction between public reproducible evidence and private source-project context.

## Next priorities

1. PostgreSQL repository and append-only audit store
2. Authentication, RBAC, and tenant isolation
3. Async tool executor with timeout and retry policy
4. OpenAI-compatible planner/provider adapter
5. CRM, email, RAG, and billing adapters
6. Evaluation fixtures and measured policy-promotion gates

## Author

Built by [o-yutaka](https://github.com/o-yutaka) as a public AI-agent engineering portfolio focused on reliable business automation.
