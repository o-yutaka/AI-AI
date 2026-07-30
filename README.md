# AI Agent Control Plane

A production-oriented portfolio for building, evaluating, and operating reliable AI agents.

This repository presents a reusable control-plane architecture extracted from a competitive decision-agent project. The original domain adapter was built for a turn-based simulation competition; the same runtime patterns apply to customer support, CRM operations, document workflows, internal search, and approval-based business automation.

## What this demonstrates

- Python agent runtime and deterministic state handling
- Hierarchical planning instead of one-shot prompt execution
- Tool/action validation before execution
- Retry, timeout, fallback, and anomaly handling
- Human approval gates for high-impact actions
- Decision, evidence, and execution audit logs
- Automated evaluation against reproducible scenarios
- Provider-independent interfaces for external engines and LLMs
- Architecture ready for FastAPI and a Next.js operations dashboard

## Architecture

```text
Business UI / Next.js Dashboard
              |
         FastAPI API
              |
      AI Control Plane
  +-----------+-----------+
  |           |           |
Planner    Evaluator    Policy Gate
  |           |           |
  +------ Agent Runtime ---+
              |
      Tool / Engine Adapter
              |
 CRM | Email | RAG | Simulation | External APIs
              |
     Audit + Evaluation Store
```

## Core execution loop

```text
Observation
    -> normalize state
    -> generate valid candidates
    -> plan routes
    -> evaluate risk and expected value
    -> enforce policy constraints
    -> execute one validated action
    -> record evidence and outcome
    -> run regression evaluation
```

## Why the competition case study matters

The source project operates under stricter constraints than a typical chatbot:

- The agent must choose only actions exposed by an external engine.
- Invalid action indexes are unacceptable.
- Hidden information cannot be treated as known.
- Multi-step selections must preserve engine semantics.
- A locally attractive action can destroy a longer route.
- Changes require regression tests and measured promotion gates.

These are directly transferable to enterprise agents that must use APIs safely, respect permissions, preserve workflow state, and produce auditable decisions.

## Portfolio case studies

| Case study | Business translation | Evidence shown |
|---|---|---|
| Competitive decision agent | Stateful AI agent runtime | Planning, option validation, policy gates |
| External engine integration | SaaS/API integration | Adapter boundaries and contract tests |
| Automated match evaluation | Agent evaluation harness | Scenario suites and regression gates |
| Decision telemetry | Operational observability | Decision reasons, rejected actions, anomalies |
| Recovery policies | Production reliability | Fallback, timeout, safe default behavior |

Read the detailed case study: [docs/case-study-pokemon.md](docs/case-study-pokemon.md)

Read the reusable architecture: [docs/architecture.md](docs/architecture.md)

## Target implementation stack

```text
Backend       Python 3.12, FastAPI, Pydantic
Frontend      Next.js, TypeScript
Execution     Async workers / queue-based jobs
Storage       PostgreSQL, structured JSON event logs
AI            OpenAI-compatible providers, local models, custom engines
Operations    Docker, pytest, GitHub Actions, metrics dashboard
Governance    Human approval, policy rules, audit trail
```

## API surface

Planned public interface:

```http
POST /v1/agents/{agent_id}/runs
GET  /v1/runs/{run_id}
POST /v1/runs/{run_id}/approve
GET  /v1/runs/{run_id}/trace
POST /v1/evaluations
GET  /v1/metrics
```

A run trace is designed to expose:

```json
{
  "goal": "complete the requested workflow safely",
  "observation": {},
  "candidates": [],
  "selected_action": {},
  "rejected_actions": [],
  "policy_checks": [],
  "evidence": [],
  "result": {},
  "latency_ms": 0,
  "status": "completed"
}
```

## Engineering principles

1. External system contracts are the source of truth.
2. The agent may select only currently valid actions.
3. Planning and execution are separate concerns.
4. Every high-impact action can require human approval.
5. Every decision must be explainable from stored evidence.
6. New policies are promoted only after regression evaluation.
7. Safe degradation is preferable to an unverified action.

## Relevance to AI engineering roles

This portfolio is intended for roles involving:

- AI agent application development
- Python and FastAPI backends
- TypeScript and Next.js operations interfaces
- LLM orchestration and tool calling
- AI automation and business-process improvement
- Agent evaluation, observability, and reliability
- Multi-provider or external-engine integration

## Repository status

The reusable public architecture and case-study documentation are available here. Competition-specific engine binaries, card data, and submission assets remain isolated from this portfolio repository.

## Next milestones

- Executable FastAPI reference runtime
- Next.js trace dashboard
- CRM and email workflow adapters
- Provider router with fallback policies
- Evaluation fixtures and CI gates
- Docker Compose demonstration environment

## Author

Built by [o-yutaka](https://github.com/o-yutaka) as a production-focused AI agent engineering portfolio.
