# Evidence and claim boundary

This file separates **publicly reproducible evidence**, **real backend integration code**, **browser simulation**, and **claims intentionally not made**.

## Fastest review path

1. Open the [interactive public proof](https://raw.githack.com/o-yutaka/AI-AI/main/docs/live-demo.html).
2. Inspect [`assets/proof/visual-proof-manifest.json`](assets/proof/visual-proof-manifest.json).
3. Read `control_plane/runtime.py`, `control_plane/security.py`, `control_plane/providers.py`, and `control_plane/tools.py`.
4. Run the locked test and Compose gates below.

## Browser proof: real lifecycle, simulated integrations

The public browser demo executes these mechanisms locally:

- canonical SHA-256 request and observation fingerprints
- current action-contract enforcement
- permission enforcement
- high-risk evidence requirement
- exact tool/operation capability enforcement
- deterministic candidate ranking and rejection reasons
- high-impact approval and rejection
- stable idempotency keys
- duplicate replay without a second execution
- conflicting-request rejection
- execution count and audit-event revision

Provider generation and external tool execution are intentionally simulated in the browser. The page has `connect-src 'none'`, requires no secret, and performs no external side effect.

The Chromium proof workflow verified:

```json
{
  "different_run_ids_same_input": true,
  "duplicate_execution_count": 1,
  "blocked_execution_count": 0,
  "conflict_execution_count": 0,
  "approved_execution_count": 1
}
```

The exact fingerprint, image dimensions, and generated assets are recorded in [`assets/proof/visual-proof-manifest.json`](assets/proof/visual-proof-manifest.json).

## Real backend implementation

### Runtime and state

- FastAPI and Pydantic request/response boundary
- contract, permission, evidence, sensitive-data, and tool-capability gates
- deterministic ranking and tie-breaking
- approval/rejection lifecycle
- explicit execution-attempt count
- idempotent replay and conflicting-request rejection
- canonical fingerprints independent of run ID
- structured external-execution failure traces
- SQLite persistence with restart-safe approvals and idempotency
- defensive-copy repository reads

### Provider boundary

- real HTTP requests to an operator-configured OpenAI-compatible `/chat/completions` endpoint
- temperature-zero JSON candidate request
- observation and goal redaction before provider transmission
- candidate schema validation
- undeclared tool/operation rejection
- disabled redirects
- timeout and response-byte limit enforced while streaming
- redacted provider errors

Tests use `httpx.MockTransport`; the repository does not claim a public production provider deployment.

### Tool boundary

- real HTTP requests through operator-configured adapters
- exact tool and operation registry
- fixed base URL, HTTP method, and relative path template
- URL-encoded scalar path parameters
- sensitive payload rejection before transmission
- sensitive headers restricted to environment-variable references
- disabled redirects
- timeout and response-byte limit enforced while streaming
- nested sensitive-field redaction in returned JSON
- structured execution failure in the trace

Tests use `httpx.MockTransport`; no vendor credential or customer endpoint is committed.

### Privacy and security boundary

- default sensitive-key set for authorization, cookies, passwords, secrets, tokens, API keys, email, phone, and address variants
- configurable domain-specific sensitive keys
- nested mapping/list redaction
- free-text bearer, credential assignment, email, and phone redaction
- action payloads containing detected sensitive values are blocked rather than silently rewritten and executed
- redaction before provider transmission, persistence, API return, approval/audit recording, and error recording
- CORS allow-list plus `nosniff`, frame denial, no-referrer, and restrictive permissions headers

This is application-layer defense in depth, not a claim of complete data-loss prevention.

## Reproducible commands

Complete stack:

```bash
docker compose up --build
```

Locked Python verification:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
pip install --no-deps -e .
ruff check .
pytest -q
```

Locked frontend verification:

```bash
cd web
npm ci
npm run build
```

Browser proof:

```bash
python -m http.server 4173 --directory docs
python scripts/capture_visual_proof.py \
  --url http://127.0.0.1:4173/live-demo.html \
  --output docs/assets/proof
```

## Delivery evidence

GitHub Actions covers:

- Python 3.11 and 3.12
- Ruff and pytest
- npm lockfile build and static export
- backend/runtime-lock Docker image
- frontend/npm-lock Docker image
- Compose health and dashboard smoke
- Chromium interaction verification
- desktop/mobile screenshot and GIF generation
- dependency-lock freshness

Images are committed for durable review; generated workflow artifacts are supplementary.

## Deployment truth

The immediate mirror and its HTTP status are tracked in [`live-status.json`](live-status.json).

The clean GitHub Pages URL is prepared but must not be described as live until repository-level Pages is enabled and the status file records successful build, deployment, HTTP verification, and status `200`.

## Source-project context not reproduced here

The original competition project contains domain-specific engine adapters, policy code, match traces, search components, and submission assets. This repository extracts the transferable control-plane pattern; it is not a public reproduction of the entire competition system.

## Claims intentionally not made

This repository does not claim:

- production authentication, enterprise RBAC, or tenant isolation
- PostgreSQL, distributed queues, multi-region replication, or distributed transactions
- bundled CRM, billing, email, RAG, or ticketing vendor connectors
- production customer traffic or deployment history
- load-test evidence or production SLOs
- audited regulatory compliance or security certification
- complete prevention of every possible secret or personal-data encoding

## Evidence rule

```text
Claim → source file → test or command → generated artifact/log → explicit limitation
```
