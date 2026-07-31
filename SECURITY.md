# Security policy

## Supported versions

Security fixes are applied to the latest release and the `main` branch.

| Version | Supported |
|---|---|
| 0.5.x | Yes |
| 0.4.x and earlier | No |

## Reporting a vulnerability

Do not publish credentials, customer data, exploit payloads, or complete reproduction details in a public issue.

Use GitHub's private vulnerability reporting flow for this repository when the **Report a vulnerability** button is available under the Security tab. Include:

- affected commit or release
- impact and attack preconditions
- the smallest safe reproduction
- whether secrets or personal data may have been exposed
- a suggested remediation, when known

If private reporting is unavailable, open a public issue containing only the title `Private security contact requested` and a non-sensitive summary. Wait for a private contact path before sharing technical details.

## Scope

High-priority reports include:

- bypass of contract, permission, approval, idempotency, or tool allow-list gates
- SSRF, redirect, path-template, or arbitrary-host execution
- secret or personal-data persistence without redaction
- unbounded provider or tool responses
- cross-origin access outside configured origins
- duplicate irreversible side effects

This repository is a reference implementation and does not claim audited compliance or production certification.
