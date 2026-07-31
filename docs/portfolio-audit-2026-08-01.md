# Portfolio audit — 2026-08-01

This audit reviews the repository as a hiring portfolio, not only as a codebase. Findings are separated into verified strengths, current blockers, and promotion gates.

## Verified strengths

- The immediate public mirror is independently checked by GitHub Actions and currently records HTTP 200.
- The browser demo is self-contained, responsive, and prevents external network calls through CSP.
- The backend separates untrusted provider output from runtime authorization and execution.
- Tool adapters use exact tool and operation registration, fixed operator-configured hosts, disabled redirects, timeouts, and structured failures.
- High-impact actions pause before execution and require a named approval or rejection.
- SQLite persistence preserves runs, approvals, and idempotency records across process restarts.

## P0 — portfolio truth and public proof

### 1. Enable repository-level GitHub Pages

Current state: code and workflow are ready, but repository-level Pages is not enabled. The clean URL must not be described as live until `docs/live-status.json` records:

```json
{
  "pages_build_result": "success",
  "pages_deploy_result": "success",
  "pages_verification_result": "success",
  "pages_http_status": "200"
}
```

### 2. Replace the low-resolution screenshot

The current JPEG is 424 × 383 pixels. It proves that a UI exists but is too small for a reviewer to read policy checks, rejection reasons, and trace identity.

Promotion gate:

- desktop screenshot at 1440 × 1000 or larger
- mobile screenshot at 390 × 844 or larger
- approval-waiting state visible
- one completed or rejected state visible
- text readable without browser zoom

### 3. Make public-demo fingerprints deterministic

The static HTML and Next.js demo currently derive fingerprints from the random run ID. Re-running the same input therefore creates a different fingerprint, which conflicts with the repository's deterministic-fingerprint claim.

Promotion gate:

- fingerprint canonical input, not run identity
- same input produces the same observation and request fingerprints
- changed input produces a different fingerprint
- regression tests cover both conditions

### 4. Label simulated and real execution surfaces explicitly

The public demo simulates provider candidates and execution locally. The repository contains real OpenAI-compatible and HTTP adapter implementations, but the public page must not visually imply that the browser demo contacted those systems.

Required top-of-page wording:

```text
Public simulation: real contract, policy, approval, and trace lifecycle; simulated provider and executor; no external network calls.
```

## P1 — missing proof scenarios

### 5. Demonstrate a blocked action

The current public demo shows successful execution and approval/rejection, but not the most important safety property: refusing an invalid action.

Add at least one scenario for:

- action ID outside the current contract
- missing permission
- high-risk action without evidence
- unregistered tool or operation

The expected result is `blocked`, no executor event, and an exact rejection reason.

### 6. Demonstrate idempotency visibly

Idempotency exists in the backend but is not visible in the public review path. Add a replay button using a stable idempotency key and show:

- duplicate request returns the existing run
- conflicting request with the same key is rejected
- no second execution event is created

### 7. Add a short GIF or two-state image sequence

A static screenshot does not demonstrate the critical transition:

```text
waiting_approval → approved/rejected → execution/no execution → revised audit trace
```

Keep it under 15 seconds and show no secrets or external customer data.

## P1 — implementation hardening

### 8. Enforce response limits while streaming

`HttpJsonToolAdapter` currently loads `response.content` before checking `max_response_bytes`. This is post-download validation, not a network or memory bound.

Promotion gate:

- stream response chunks
- abort immediately after the configured threshold
- add tests for a response that crosses the threshold incrementally
- update README wording only after the streaming gate passes

Apply the same bounded-read principle to provider responses.

### 9. Add payload and result redaction

Real support and billing integrations can place PII, credentials, and tokens in observations, payloads, errors, or tool responses. Add a redaction boundary before persistence, API responses, and logs.

Minimum gate:

- configured sensitive-key list
- Authorization, cookie, token, secret, password, and API-key defaults
- nested mapping/list redaction
- tests proving persisted traces contain no raw secret

### 10. Commit a frontend lockfile

`web/package-lock.json` is absent, so CI uses dependency resolution rather than a committed dependency graph.

Promotion gate:

- commit `web/package-lock.json`
- replace `npm install` with `npm ci` in CI and Pages workflows
- verify local, CI, Docker, and static export use the same lockfile

## P2 — reviewer experience

- Add visible keyboard focus styles and `aria-live` for run-state changes.
- Add one-click links from the demo to architecture, tests, and claim boundaries.
- Add a concise “What is real here?” panel above the fold.
- Add release tags and a changelog for portfolio milestones.
- Add dependency and code-security scanning without claiming compliance certification.

## Repository-level account actions

These cannot be completed by a code commit and require GitHub UI access:

1. Enable Pages with GitHub Actions as the source.
2. Pin `AI-AI`, `BLACK`, and `black-pokemon-championship` on the profile.
3. Archive or privatize obsolete public repositories after preserving any unique work.

## Promotion rule

The public portfolio is considered complete only when:

```text
clean Pages URL HTTP 200
+ readable desktop/mobile evidence
+ deterministic demo fingerprints
+ blocked-action demonstration
+ visible idempotency demonstration
+ streaming response limits
+ secret/PII redaction
+ lockfile-reproducible frontend build
+ actual profile pins verified
```
