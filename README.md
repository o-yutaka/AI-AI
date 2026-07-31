# AI Agent Control Plane

[![CI](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/o-yutaka/AI-AI/actions/workflows/ci.yml)
[![Live demo](https://img.shields.io/badge/live-demo-b9ff66?style=flat&labelColor=10150a)](https://o-yutaka.github.io/AI-AI/)

A working full-stack reference system for **contract-aware, auditable, human-approved AI agents**.

**Live interactive demo:** https://o-yutaka.github.io/AI-AI/

The public browser demo requires no API key and performs no external side effect. It reproduces candidate generation, contract checks, deterministic selection, approval gating, rejection reasons, execution state, and the audit timeline. The backend supports an OpenAI-compatible planner and allow-listed HTTP tool adapters for real integrations.

[![AI Agent Control Plane approval screen](docs/assets/ai-agent-control-plane-live.jpg)](https://o-yutaka.github.io/AI-AI/)

## What this proves

| Concern | Implemented evidence |
|---|---|
| LLM integration | OpenAI-compatible `/chat/completions` candidate planner |
| Model boundary | Model proposes candidates; it never receives direct execution authority |
| Tool execution | Fixed-host, fixed-method, fixed-path HTTP JSON adapters |
| API and validation | FastAPI + Pydantic request/response contracts |
| Allowed action boundary | Versioned action contract and allow-list filtering |
| Authorization | Per-action permission requirements |
| High-impact safety | Evidence requirement plus named human approval/rejection |
| Deterministic decisions | Stable ranking, tie-breaking, and request fingerprints |
| Duplicate prevention | Idempotency key with conflicting-request detection |
| Auditability | Timestamped events, policy checks, rejected reasons, revisions |
| Failure handling | Provider and executor failures recorded as structured errors |
| Restart safety | Pluggable repository with durable SQLite implementation |
| Full-stack operations | Next.js dashboard for run, review, approval, and trace inspection |
| Public delivery | Static interactive GitHub Pages demo plus Docker Compose |
| Verification | Python 3.11/3.12, Ruff, Next.js build, and two Docker builds in CI |

## Try the public flow

1. Open the live demo.
2. Run the low-risk workflow and inspect the selected action and lower-ranked rejection.
3. Run the approval-gated refund.
4. Verify that the high-impact action has not executed.
5. Approve or reject it and inspect the revised trace and audit events.

The Pages deployment intentionally uses a browser-local executor. This makes the portfolio safe to operate publicly while preserving the same visible decision and approval lifecycle.

## Run the complete stack

```bash
docker compose up --build
```

Open:

- Dashboard: `http://localhost:3000`
- FastAPI/OpenAPI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Docker Compose configures `AGENT_DB_PATH=/data/control-plane.sqlite3` and a named volume. Completed runs, pending approvals, and idempotency records remain available after the API container restarts.

## Architecture

```text
Next.js Operations Dashboard
             |
          FastAPI
             |
  OpenAI-compatible Planner
     candidate generation
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
   ToolRegistryExecutor
             |
 allow-listed HTTP adapters
             |
  audit events + result/error
             |
      RunRepository
       /          \
  in-memory      SQLite
```

The two critical trust boundaries are deliberate:

1. Provider output is untrusted `CandidateAction` input and must pass the existing contract, permission, evidence, ranking, approval, and idempotency gates.
2. A selected action can execute only through an adapter registered under an exact tool name. The model cannot choose a host, HTTP method, arbitrary path, redirect target, or secret.

See:

- [`docs/adr/0001-durable-run-store.md`](docs/adr/0001-durable-run-store.md)
- [`docs/adr/0002-provider-tool-boundary.md`](docs/adr/0002-provider-tool-boundary.md)

## OpenAI-compatible planner

Configure any endpoint that implements the OpenAI-style chat-completions request shape:

```bash
export OPENAI_COMPATIBLE_BASE_URL="https://provider.example/v1"
export OPENAI_COMPATIBLE_MODEL="your-model"
export OPENAI_COMPATIBLE_API_KEY="your-key"
```

PowerShell:

```powershell
$env:OPENAI_COMPATIBLE_BASE_URL = "https://provider.example/v1"
$env:OPENAI_COMPATIBLE_MODEL = "your-model"
$env:OPENAI_COMPATIBLE_API_KEY = "your-key"
```

Provider status:

```bash
curl http://localhost:8000/v1/provider
```

Create a provider-planned run through `POST /v1/agent-runs`. The request supplies the goal, observation, current action contract, and tool capability catalog. The provider returns candidates only; the runtime remains the authority.

## Real HTTP tool adapters

Adapters are configured by the operator, not generated by the model. This example allows one support operation against one fixed base URL:

```json
{
  "support_api": {
    "base_url": "https://api.example.com",
    "headers": {
      "Authorization": "Bearer ${SUPPORT_API_TOKEN}"
    },
    "operations": {
      "reply": {
        "method": "POST",
        "path": "/tickets/{ticket_id}/reply",
        "payload_mode": "json"
      }
    }
  }
}
```

Set it as `TOOL_ADAPTERS_JSON` and provide `SUPPORT_API_TOKEN` separately. Runtime protections include:

- exact tool-name lookup
- exact configured operation lookup
- fixed base URL and HTTP method
- relative traversal-free path templates
- URL-encoded scalar path parameters
- environment-only secret resolution
- disabled redirects
- request timeout
- bounded response size
- structured execution failure in the decision trace

## API

```text
GET  /health
GET  /v1/provider
POST /v1/agent-runs
POST /v1/runs
GET  /v1/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/decision
```

`POST /v1/runs` accepts caller-supplied candidates for deterministic testing and integrations that already have a planner. `POST /v1/agent-runs` invokes the configured OpenAI-compatible candidate planner first.

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

## Runtime guarantees demonstrated

- Versioned external action contract
- Action allow-list enforcement
- Per-action permission checks
- High-risk evidence requirement
- Deterministic ranking and tie-breaking
- High-risk and irreversible action approval gate
- Named approval or rejection with a reason
- Idempotency protection against duplicate execution
- Conflict detection when one idempotency key is reused for different input
- Structured provider and executor failure recording
- Observation and request fingerprints
- Timestamped audit events and revision tracking
- Defensive-copy repository reads
- Restart-safe SQLite persistence without an additional database package

## Local development

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

Frontend:

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
│   ├── providers.py
│   ├── runtime.py
│   ├── store.py
│   └── tools.py
├── tests/
│   ├── test_api.py
│   ├── test_persistence.py
│   ├── test_providers.py
│   ├── test_runtime.py
│   └── test_tools.py
├── web/
│   ├── app/
│   ├── Dockerfile
│   └── package.json
├── docs/
│   ├── adr/
│   ├── assets/
│   ├── case-study-pokemon.md
│   └── evidence.md
├── .github/workflows/
│   ├── ci.yml
│   └── pages.yml
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Verification gates

GitHub Actions verifies:

- Ruff
- pytest on Python 3.11 and 3.12
- OpenAI-compatible response validation
- rejection of undeclared provider tool operations
- fixed-host HTTP adapter execution through `httpx.MockTransport`
- rejection of unregistered tools and operations
- restart-safe approval and idempotency
- Next.js production build on Node.js 22
- Backend Docker image build
- Frontend Docker image build
- GitHub Pages static export and deployment

## Transfer from strict simulation agents

The architecture was extracted from a stateful competition agent connected to a strict external engine, then translated into a business workflow instead of publishing game-specific policy as the product.

| Strict-engine constraint | Business-agent equivalent | Public implementation |
|---|---|---|
| Select only engine-provided options | Call only currently allowed tools | Versioned action contract |
| Preserve option and workflow state | Preserve transaction state | Durable run trace |
| Do not assume hidden information | Do not treat unavailable data as fact | Caller observation + fingerprint |
| Resource-sensitive decisions | Permissions, cost, rate limits | Policy metadata and checks |
| Invalid action is unacceptable | Unauthorized or unsupported API call | Candidate and adapter filtering |
| Replay and policy comparison | Audit and regression evaluation | Decision events and tests |

Read [`docs/case-study-pokemon.md`](docs/case-study-pokemon.md) for the transfer boundary.

## Claim boundary

This is a portfolio-grade reference system, not a finished enterprise platform. It demonstrates a durable single-node control plane, provider integration, and operator-configured HTTP tools, but it does **not** claim:

- production authentication, tenant isolation, or enterprise RBAC
- PostgreSQL or distributed database operation
- durable background queues
- bundled vendor-specific CRM, email, billing, or RAG connectors
- load-test evidence or production SLOs
- multi-region replication or distributed transactions

See [`docs/evidence.md`](docs/evidence.md) for the distinction between public reproducible evidence and private source-project context.

## Next priorities

1. Authentication, RBAC, and tenant isolation
2. Async execution with retry, backoff, circuit breaking, and durable queues
3. Vendor-specific CRM, email, billing, and RAG adapter packages
4. Append-only audit/event storage
5. Evaluation fixtures and measured policy-promotion gates
6. Load testing and production SLO evidence

## Author

Built by [o-yutaka](https://github.com/o-yutaka) as a public AI-agent engineering portfolio focused on reliable business automation.
