# ADR 0002: Separate model planning from tool execution

- Status: accepted
- Date: 2026-08-01

## Context

An LLM can produce useful candidate actions, but its output is probabilistic, externally supplied, and may reference unsupported tools or unsafe operations. Giving model output direct network authority would bypass the control plane's purpose.

The portfolio also needs a real integration path without embedding provider or SaaS credentials in the public browser demo.

## Decision

The system separates planning, policy, and execution into three explicit boundaries.

### 1. Provider boundary

`OpenAICompatiblePlanner` sends the current goal, observation, action contract, and a declared tool capability catalog to an OpenAI-compatible chat-completions endpoint.

The response is accepted only when it:

- contains valid JSON
- validates as one or more `CandidateAction` objects
- references only declared tool and operation pairs
- contains no more than 100 candidates

Provider output is untrusted input. It does not execute anything.

### 2. Runtime authority

Every provider candidate passes through the existing runtime controls:

- current action-contract membership
- required permission checks
- high-risk evidence requirement
- deterministic ranking and tie-breaking
- high-impact approval gate
- idempotency and request-fingerprint checks
- complete decision and failure trace

The runtime, not the provider, selects the action.

### 3. Tool adapter boundary

`ToolRegistryExecutor` resolves the selected action by exact tool name. `HttpJsonToolAdapter` then resolves the operation from operator-owned configuration.

A candidate cannot choose:

- an arbitrary host
- an arbitrary HTTP method
- an arbitrary URL path
- a redirect target
- a secret value
- an unregistered tool or operation

The adapter additionally enforces URL-encoded scalar path values, a request timeout, disabled redirects, and a bounded response size.

## Public demo boundary

GitHub Pages uses `NEXT_PUBLIC_DEMO_MODE=true`. It reproduces the decision, approval, and audit lifecycle entirely in the browser and performs no external network side effect. The real provider and HTTP adapter implementations remain reproducible in the same repository and are verified with mock transports in CI.

## Consequences

### Positive

- Provider choice can change without changing runtime policy.
- Model hallucinations cannot directly become network calls.
- Tool credentials remain operator-controlled environment values.
- Provider and adapter behavior can be tested without real secrets.
- The public demo remains safe and continuously available.

### Trade-offs

- Tool configuration is intentionally more explicit than generic agent frameworks.
- The first implementation is synchronous and single-process.
- Provider-specific responses outside the OpenAI-compatible shape require another adapter.
- Durable queues, retries, circuit breaking, and distributed execution are deferred.

## Rejected alternatives

### Let the model call arbitrary URLs

Rejected because it creates an SSRF and credential-exposure boundary and makes action authorization unverifiable.

### Encode provider calls directly in `AgentRuntime`

Rejected because it couples probabilistic planning to deterministic policy and makes provider replacement and testing harder.

### Put real credentials in the Pages demo

Rejected because browser-delivered secrets are not secrets and public interactions could create external side effects.
