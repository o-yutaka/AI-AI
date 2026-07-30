# Portfolio Map

This repository is one part of a broader AI engineering portfolio. Each project has a different purpose and evidence boundary.

## Recommended review order

### 1. BLACK

Repository: https://github.com/o-yutaka/BLACK

Use BLACK as the primary example for:

- LLM and capability routing
- Agent runtime and mission execution
- Decision verification and replay
- Evidence and audit ledgers
- Plugin and provider SDK design
- CLI and Next.js operations UI
- SQLite persistence and secrets handling
- Large test and E2E surface

BLACK demonstrates the widest system-design scope.

### 2. AI Agent Control Plane

Repository: https://github.com/o-yutaka/AI-AI

Use this repository as the fastest runnable example for:

- Python and FastAPI
- TypeScript and Next.js
- Human approval and rejection
- Contract, permission, and evidence checks
- Idempotency and conflict handling
- Decision traces
- Docker Compose
- Small, reviewable test surface

This is the best entry point for a recruiter or client who wants to understand the implementation quickly.

### 3. BLACK Pokémon Championship Agent

Repository: https://github.com/o-yutaka/black-pokemon-championship

Use this project as evidence for:

- Strict external-engine integration
- Stateful decision systems
- Valid-option enforcement
- Deterministic submission packaging
- Regression and crash screening
- Evaluation discipline

The domain is a competition, but the reusable engineering lesson is safe execution against a changing external contract.

### 4. black-core

Repository: https://github.com/o-yutaka/black-core

Supporting experimental work:

- Python autonomous loop
- Event bus
- Task and goal engines
- FAISS semantic memory
- Isolated code execution with timeout and captured output

Do not use this as the first portfolio link until its tests, CI, documentation, and evidence are strengthened.

## Role mapping

| Target role | Primary project | Supporting project |
|---|---|---|
| AI Agent application engineer | AI-AI | BLACK |
| LLM platform / orchestration engineer | BLACK | AI-AI |
| Python / FastAPI AI engineer | AI-AI | black-core |
| TypeScript / Next.js AI engineer | BLACK | AI-AI |
| Evaluation / planning / simulation engineer | black-pokemon-championship | BLACK |
| AI automation consultant | AI-AI | BLACK |

## Projects intentionally excluded from the main portfolio

Empty repositories, lightly modified forks, duplicate experiments, and projects without a clear evidence boundary should not be presented as primary work. More repositories do not create a stronger portfolio; a small set of reproducible, clearly differentiated projects does.
