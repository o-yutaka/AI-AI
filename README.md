# AI Agent Control Plane

An executable, production-oriented reference for building **stateful, auditable, approval-aware AI agents** with Python and FastAPI.

The architecture is extracted from a competitive decision-agent project connected to a strict external simulation engine. The reusable patterns apply to customer support, CRM operations, document workflows, internal search, and approval-based business automation.

## Current implementation

This repository now includes working code for:

- Typed agent and action contracts with Pydantic
- Deterministic candidate selection
- Policy gates for high-risk or irreversible actions
- Human approval before execution
- Decision traces containing candidates, rejected actions, policy checks, and results
- FastAPI endpoints for creating, reading, and approving runs
- Unit tests for normal execution and approval-gated execution
- Docker packaging
- GitHub Actions CI with Ruff and pytest

It does **not** yet include the planned Next.js dashboard, persistent PostgreSQL storage, a real LLM provider router, or production authentication. Those remain explicit milestones rather than being presented as completed work.

## Architecture

```text
Client / future Next.js dashboard
              |
          FastAPI API
              |
       Agent Runtime
   +----------+-----------+
   |          |           |
Selector   Policy Gate   Audit Trace
   |          |           |
   +------ Validated Action
              |
        Tool / API Adapter
```

The larger reusable architecture is documented in [docs/architecture.md](docs/architecture.md).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app:app --reload
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app:app --reload
```

Open the interactive API documentation at `http://127.0.0.1:8000/docs`.

## Docker

```bash
docker build -t ai-agent-control-plane .
docker run --rm -p 8000:8000 ai-agent-control-plane
```

## API example

Create a low-risk run that can execute immediately:

```bash
curl -X POST http://127.0.0.1:8000/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Resolve a customer support request",
    "observation": {"customer_tier": "standard"},
    "candidates": [
      {
        "action_id": "reply",
        "name": "Send approved response",
        "expected_value": 0.8,
        "risk": "low",
        "reversible": true,
        "evidence": ["knowledge-base/article-12"]
      },
      {
        "action_id": "escalate",
        "name": "Escalate to operator",
        "expected_value": 0.5,
        "risk": "low",
        "reversible": true
      }
    ]
  }'
```

A high-risk or irreversible selected action returns `waiting_approval` and is not executed until:

```bash
curl -X POST http://127.0.0.1:8000/v1/runs/<run_id>/approve
```

## API surface

```text
GET  /health
POST /v1/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/approve
```

## Core execution contract

```text
Observation
    -> receive only caller-provided candidates
    -> select the strongest current candidate
    -> record rejected alternatives
    -> apply risk and reversibility policy
    -> pause for approval when required
    -> execute one validated action
    -> preserve the complete trace
```

The reference runtime intentionally does not invent tools or actions. In a production adapter, candidate actions must come from the current external API contract and user permissions.

## Why the competition case study matters

The source project operates under constraints stricter than a normal chatbot:

- The agent may select only actions exposed by the external engine.
- Invalid action indexes are unacceptable.
- Hidden information cannot be treated as known.
- Multi-step selections must preserve engine semantics.
- A locally attractive action can destroy a longer route.
- Changes require regression tests and measured promotion gates.

Those constraints map directly to enterprise agents using APIs, permissions, approvals, workflow state, and audit evidence.

Read the detailed transfer analysis in [docs/case-study-pokemon.md](docs/case-study-pokemon.md).

## Repository structure

```text
.
├── app.py                       FastAPI boundary
├── control_plane/
│   ├── models.py                Typed contracts and traces
│   └── runtime.py               Selection, policy, approval, execution
├── tests/test_runtime.py        Runtime regression tests
├── docs/architecture.md         Target reusable architecture
├── docs/case-study-pokemon.md   Competition-to-enterprise translation
├── Dockerfile
├── pyproject.toml
└── .github/workflows/ci.yml
```

## Test

```bash
pytest -q
ruff check .
```

## Engineering principles

1. External system contracts are the source of truth.
2. The agent may execute only currently valid actions.
3. Planning, policy validation, and execution are separate concerns.
4. High-impact actions require explicit approval.
5. Every decision preserves alternatives, evidence, and policy outcomes.
6. Policy changes require regression evaluation before promotion.
7. Safe degradation is preferable to an unsupported action.

## What this proves to an employer

- Python backend and typed domain modeling
- FastAPI service design
- Stateful AI-agent execution
- Human-in-the-loop workflow control
- Auditability and rejected-action reasoning
- Testable policy behavior
- Docker and CI fundamentals
- Ability to translate a strict decision-agent system into business automation architecture

## Next milestones

- PostgreSQL-backed run and audit storage
- Authentication, authorization, and tenant isolation
- Idempotency and concurrent-run protection
- Retry, timeout, and structured tool-error handling
- OpenAI-compatible provider adapter with fallback policies
- Evaluation fixtures and measured promotion gates
- Next.js trace and operations dashboard
- CRM, email, RAG, and ticketing adapters

## Author

Built by [o-yutaka](https://github.com/o-yutaka) as an AI-agent engineering portfolio focused on reliable business automation.
