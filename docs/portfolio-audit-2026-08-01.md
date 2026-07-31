# Portfolio audit — 2026-08-01

This audit reviews the repository as a hiring portfolio, not only as a codebase. Code-side findings are closed only when source, tests, generated evidence, and claim boundaries agree.

## Final code-side verdict

```text
CODE_SIDE_PORTFOLIO_GATES: PASS
ACCOUNT_LEVEL_GITHUB_GATES: HOLD
```

Machine-readable browser proof: [`assets/proof/visual-proof-manifest.json`](assets/proof/visual-proof-manifest.json).

## Closed P0 findings

### Readable visual evidence — PASS

Committed proof assets now include:

- desktop waiting approval: 1440 × 1895
- desktop approved: 1440 × 1979
- desktop blocked: 1440 × 2047
- desktop idempotency replay: 1440 × 1937
- mobile waiting approval: 390 × 3841
- compact proof GIF: 640 × 600

The images are generated from the operational public demo by Chromium, not manually composed screenshots.

### Deterministic browser fingerprints — PASS

The browser implementation hashes canonical input with SHA-256. Run identity is excluded.

The proof workflow creates two different run IDs from the same request and asserts the same request fingerprint. Python tests separately verify canonical key ordering and changed-input sensitivity.

### Simulation boundary — PASS

The public page displays `PUBLIC SIMULATION` and an above-the-fold “What is real here?” panel.

The page explicitly states:

- policy, approval, blocking, idempotency, fingerprint, and trace lifecycle execute in-browser
- provider generation is simulated
- tool execution is simulated
- Content Security Policy disables external network calls

The repository documents the separate real HTTP provider and adapter implementations without claiming the browser contacted them.

## Closed P1 proof findings

### Blocked-action proof — PASS

The public demo and backend tests cover:

- action outside the current contract
- missing permission
- high-risk action without evidence
- unregistered tool or operation
- sensitive values in action payloads

Expected behavior is exact rejection reasons, status `blocked`, and execution count `0`.

### Idempotency proof — PASS

The public demo and backend expose:

- stable idempotency key
- request fingerprint
- replay of the same request returning the existing run
- `idempotency_replayed=true`
- execution count remaining `1`
- conflicting request rejection
- conflict execution count `0`

### Approval-transition proof — PASS

The Chromium workflow verifies:

```text
waiting approval, execution count 0
→ approve
→ completed, execution count 1
```

The GIF and desktop images preserve the review sequence.

## Closed P1 implementation findings

### Streaming response limits — PASS

Provider and HTTP tool responses are consumed incrementally. Reading stops as soon as the configured byte limit is crossed. Tests cover oversized responses.

### Sensitive-data boundary — PASS within stated scope

Implemented controls:

- default and operator-configured sensitive keys
- nested mapping/list redaction
- bearer, credential-assignment, email, and phone free-text redaction
- observation and goal redaction before provider transmission
- sensitive action-payload rejection before execution
- result, error, approval, audit, persistence, and API-return redaction
- sensitive HTTP headers restricted to environment-variable references

This is defense in depth, not a claim of complete DLP or regulatory compliance.

### Dependency reproducibility — PASS

Committed files:

- `requirements.runtime.lock.txt`
- `requirements.lock.txt`
- `web/package-lock.json`

CI, Docker, local commands, frontend builds, and Pages builds use committed dependency graphs.

## Closed P2 reviewer-experience findings

- visible keyboard focus styles
- `aria-live` for run status and errors
- one-click source and claim-boundary links
- “What is real here?” panel above the fold
- release changelog
- MIT license
- security reporting policy
- weekly dependency update monitoring
- CI concurrency cancellation for stale runs
- non-root containers, health checks, read-only filesystems, and `no-new-privileges`

## Verification values

The committed manifest records:

```json
{
  "different_run_ids_same_input": true,
  "duplicate_execution_count": 1,
  "blocked_execution_count": 0,
  "conflict_execution_count": 0,
  "approved_execution_count": 1
}
```

## Remaining account-level GitHub actions

These are not code gaps and cannot be truthfully marked complete by a repository commit:

1. Enable repository-level GitHub Pages with GitHub Actions as the source.
2. Verify the clean Pages URL returns HTTP 200 and update `docs/live-status.json` through the deployment workflow.
3. Set actual profile pins for `AI-AI`, `BLACK`, and `black-pokemon-championship`.
4. Archive or privatize obsolete repositories only after unique-code review.

## Promotion rule

```text
CODE COMPLETE
  readable desktop/mobile/GIF proof
  deterministic fingerprints
  blocked-action proof
  visible idempotency proof
  streaming response limits
  sensitive-data boundary
  committed dependency locks
  browser + API + Docker + Compose verification

ACCOUNT HOLD
  clean Pages URL HTTP 200
  actual profile pins verified
```

No account-level setting is represented as complete until independently observed.
