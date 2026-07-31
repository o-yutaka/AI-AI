# Changelog

All notable changes are documented in this file.

## [0.5.0] - 2026-08-01

### Added

- deterministic browser fingerprints over canonical request input
- public blocked-action scenarios with exact rejection reasons
- visible idempotency replay and conflicting-request proof
- explicit public-simulation boundary above the fold
- sensitive-key detection and recursive trace redaction
- runtime rejection of sensitive action payloads
- runtime tool-capability allow-list enforcement
- streaming response limits for provider and HTTP tool responses
- security response headers
- MIT license, security policy, dependency monitoring, and environment template
- desktop, mobile, approval, blocked, and idempotency visual-proof generation

### Changed

- version raised to 0.5.0
- provider instructions require stable identifiers instead of credentials or personal data
- public demo and Next.js dashboard expose execution count and replay state
- Pages retry cadence reduced while repository-level Pages is disabled

### Security

- external response bodies are stopped while streaming after the configured byte limit
- nested token, credential, email, phone, and address fields are redacted
- unregistered tool operations are blocked before execution when a registry is configured

## [0.4.0] - 2026-07-31

- OpenAI-compatible candidate planner
- fixed-host HTTP tool adapters
- public interactive mirror
- GitHub Pages workflow and deployment evidence

## [0.3.0] - 2026-07-31

- SQLite persistence
- restart-safe approvals and idempotency
