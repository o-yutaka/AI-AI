# Evidence and Claim Boundary

This repository separates **publicly reproducible evidence** from claims about the private competition source project.

## Publicly reproducible in this repository

- FastAPI endpoints for creating, listing, reading, approving, and rejecting runs
- Contract allow-list enforcement
- Permission enforcement
- Evidence requirement for high-risk actions
- Deterministic candidate ranking
- Human approval and rejection records
- Idempotent run creation
- Structured executor-failure traces
- Defensive-copy storage behavior
- Unit and API tests
- Python 3.11 and 3.12 CI configuration
- Docker image build configuration

Run:

```bash
pip install -e ".[dev]"
ruff check .
pytest -q
docker build -t ai-agent-control-plane .
```

## Source-project evidence not published here

The original competition repository contains domain-specific engine adapters, policy code, match traces, and submission assets. Those assets are intentionally not copied into this portfolio repository. Therefore this public repository presents the transferable runtime pattern, not a reproducible copy of the full competition system.

## Claims intentionally not made

This repository does not claim to provide:

- A production-ready database
- Authentication or multi-tenant authorization
- A deployed Next.js dashboard
- A real CRM, email, RAG, or payment integration
- A live LLM provider router
- Distributed workers or durable queues
- Production SLOs or load-test results

Those are roadmap items and must not be described as completed work until corresponding code and evidence exist.
