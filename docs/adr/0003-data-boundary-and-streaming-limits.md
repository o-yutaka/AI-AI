# ADR 0003: Data boundary and streaming response limits

- Status: Accepted
- Date: 2026-08-01

## Context

An AI-agent control plane can expose sensitive values through several paths:

- caller observations and goals sent to a model provider
- model-generated action payloads
- HTTP authentication headers
- tool responses and external errors
- approval identities and reasons
- persisted traces and API responses

Timeouts alone do not bound memory or network response bodies. Checking body length after `response.content` has loaded is also insufficient because the full response has already entered process memory.

## Decision

### 1. Preserve decision identity over original input

Observation and request fingerprints are calculated from canonical original input before display redaction. This preserves stable idempotency and audit identity.

Run IDs, timestamps, and other runtime identity are excluded from the canonical request fingerprint.

### 2. Redact before crossing trust boundaries

Sensitive values are redacted before:

- provider transmission
- persistence
- API return
- approval and audit recording
- external-error recording

The default sensitive set covers authorization, cookie, password, secret, token, API-key, email, phone, and address variants. Operators can add domain-specific keys.

Nested mappings and lists are traversed. Free text is checked for bearer credentials, credential assignments, email addresses, and phone-like values.

### 3. Block sensitive action payloads

Action payloads containing detected sensitive values are rejected before ranking and execution.

The runtime does not silently replace a sensitive value with `[REDACTED]` and then execute a semantically altered action. Callers must use stable record identifiers; adapters resolve secrets independently from environment variables.

### 4. Restrict sensitive HTTP headers to environment references

Sensitive adapter headers such as `Authorization` and API keys must contain `${ENV_VAR}` references. Literal sensitive values in adapter configuration are invalid.

The resolved header values are never returned in the execution result or trace.

### 5. Bound responses while streaming

Provider and tool responses are consumed incrementally. The reader tracks cumulative bytes and aborts immediately after the configured maximum.

Redirects remain disabled, and timeouts remain independent controls.

### 6. Keep claims limited

These controls are defense in depth. They are not presented as complete DLP, regulatory compliance, or protection against every possible encoding or domain-specific identifier.

## Consequences

### Positive

- sensitive provider input is reduced
- raw credentials are not committed in adapter configuration
- detected sensitive action payloads cannot execute
- persisted and returned traces have a common redaction boundary
- response limits constrain memory use before the complete body loads
- decision fingerprints remain stable and reproducible

### Trade-offs

- free-text detectors can produce false positives
- sensitive values hidden in unknown encodings may evade generic detection
- blocking payloads requires integrations to use identifiers instead of direct personal data
- canonical original-input fingerprints can be correlatable and therefore require access control in a production deployment

## Verification

Relevant tests:

- `tests/test_security.py`
- `tests/test_hardening.py`
- `tests/test_provider_privacy.py`
- `tests/test_tool_config_security.py`
- `tests/test_providers.py`
- `tests/test_tools.py`
- `tests/test_trace_execution_proof.py`

Relevant implementation:

- `control_plane/security.py`
- `control_plane/providers.py`
- `control_plane/tools.py`
- `control_plane/runtime.py`
