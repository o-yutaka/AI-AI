# Kaggle AI Agent Security Lab Architecture

The canonical architecture is frozen in [`KAGGLE_SECURITY_LAB_ARCHITECTURE.md`](KAGGLE_SECURITY_LAB_ARCHITECTURE.md).

## Implemented runtime boundary

```text
FastAPI / caller
    -> typed RunRequest
    -> untrusted CandidateAction set
    -> current action contract
    -> permission / evidence / sensitive-data gates
    -> declared tool-capability gate
    -> deterministic ranking
    -> approval or rejection
    -> fixed ToolRegistryExecutor
    -> durable audit / fingerprint / replay state
```

The existing `control_plane/` package is the lab's deterministic evaluation runtime. It is retained as a reusable environment for controlled multi-step agent-tool experiments.

## Implemented invariants

1. Candidate IDs must be unique.
2. An action outside the current contract cannot execute.
3. Required permissions must be granted.
4. High-risk actions require evidence.
5. Sensitive payloads are rejected before execution.
6. Undeclared tool operations are rejected.
7. High-risk or irreversible actions require a named human decision.
8. A rejected action is never executed.
9. Repeating the same request with the same idempotency key does not execute twice.
10. Reusing an idempotency key for different input is rejected.
11. Request fingerprints are canonical and deterministic.
12. Candidate tie-breaking is deterministic.
13. Model output cannot choose arbitrary hosts, methods, paths, redirect targets, or credentials.
14. Streaming provider/tool responses are bounded.

## Research export boundary

`research_bundle/` is the only canonical external knowledge contract.

It exports `security-research-bundle.v1` containing research objects such as hypotheses, probes, observations, trajectories, findings, failure findings, robustness results, benchmark results, provenance, and artifact hashes.

It deliberately does not export BLACK `Experience`, BLACK `Lesson`, held-out verification, promotion/adoption decisions, or execution authority.

```text
control_plane experiment
    -> trace / replay
    -> analysis
    -> research_bundle
    -> canonical JSON + SHA-256
    -> external consumer
```

See the canonical document for the BLACK compatibility boundary and future module layout.
