# Case Study: Competition Agent as a Business-Automation Pattern

## Context

The source project is a decision agent connected to an official turn-based simulation engine. At each decision point the engine exposes an observation and the actions currently available. The agent must return a valid choice under strict runtime constraints.

This public repository does **not** copy the private engine, submission bundle, card data, or competition-specific policy code. It implements the transferable control-plane pattern with a customer-support example that can be run and tested publicly.

## Transferable engineering problem

A naive agent can score all visible actions and choose the highest number. That is insufficient when:

- An action is not present in the current external contract
- The caller lacks permission to execute it
- A high-impact action lacks evidence
- A multi-step workflow requires approval before execution
- An immediate gain damages a longer route
- Duplicate execution would produce a second side effect
- An external tool times out or raises an error

## Mapping

| Competition constraint | Business-agent equivalent | Public implementation |
|---|---|---|
| Engine-provided valid options | Current API/tool allow-list | `ActionContract.allowed_action_ids` |
| Hidden or unavailable state | Unverified business data | Observation is caller-supplied and fingerprinted |
| Action-specific requirements | User/API permissions | `required_permissions` gate |
| High-impact resource use | Refund, deletion, external message | Risk, evidence, reversibility, approval gate |
| Option selection | Deterministic action ranking | Explicit rank order with tests |
| Repeated engine step | Duplicate side effect | Idempotency key |
| Engine error | SaaS/API failure | Structured `ExecutionError` and failed trace |
| Match replay | Agent execution trace | Timestamped audit events and stored decision trace |

## Public execution path

```text
Observation
    + current contract
    + granted permissions
    + typed candidates
        -> reject unavailable actions
        -> reject actions with missing permissions
        -> reject high-risk actions without evidence
        -> deterministically rank remaining actions
        -> request approval for high-impact action
        -> approve or reject with identity and reason
        -> execute once
        -> preserve result or structured failure
```

## What the source project adds

The private source project applies related ideas to a much larger domain-specific state and action space, including multi-step engine selections, longer-horizon route planning, policy comparison, replay analysis, and regression gates. Those claims are contextual background rather than public reproducible evidence in this repository.

## What an employer can verify here

An employer can clone this repository and verify:

- FastAPI request validation
- Contract and permission enforcement
- High-risk evidence policy
- Human approval and rejection paths
- Deterministic decision behavior
- Duplicate-execution protection
- Structured failure recording
- Unit and HTTP API tests
- Docker and CI configuration

The distinction matters: the competition work explains where the architecture came from; the code in this repository is the evidence that can be inspected and executed publicly.
