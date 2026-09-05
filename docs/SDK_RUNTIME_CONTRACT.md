# SDK and runtime contract

The competition surface changed during the event, so runtime assumptions are treated as versioned evidence rather than magic constants.

## Host FAQ profile

The built-in profile `kaggle-host-faq-9000-v1` records the competition-host FAQ update:

- target models: `gpt_oss`, `gemma`
- 9,000 seconds per model per phase
- 15-hour global notebook runtime
- 2,000 maximum candidates
- 32 maximum user messages per candidate
- 8 maximum tool hops per `interact()` call

Primary host source:

`https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/discussion/712642`

The competition Overview has also shown an 18,000-second figure, while an SDK-discrepancy thread reported `run(env)` vs `run(env, run_config)` and a 10,000-vs-2,000 user-message-character disagreement. Those disagreements are deliberately **not** silently resolved by code.

Discrepancy thread:

`https://www.kaggle.com/competitions/ai-agent-security-multi-step-tool-attacks/discussion/733119`

## Contract identity

`CompetitionRuntimeContract` records:

- contract ID
- evidence tier
- source reference
- per-model attack-generation/public-replay/private-replay budgets
- SDK version when known
- run signature when known
- global runtime limit
- candidate/message/tool-hop limits
- optional per-user-message character limit

Every contract has a canonical SHA-256 fingerprint. Changing a budget, SDK signature, tokenizer-adjacent limit, or any other contract field changes the fingerprint.

## Fail closed

Unknown values remain unknown. For example, the host FAQ profile leaves `run_signature = UNKNOWN` and `max_user_message_chars = None` because the host FAQ itself does not establish those SDK details.

A locally inspected or pinned SDK can supply an explicit contract such as:

```json
{
  "contract_id": "sdk-observed-v1",
  "evidence_tier": "SDK_OBSERVED",
  "source_ref": "local-sdk-inspection",
  "sdk_version": "3.1.2",
  "run_signature": "ENV_AND_RUN_CONFIG",
  "model_phase_budgets": {
    "gpt_oss": {
      "attack_generation_s": 9000,
      "public_replay_s": 9000,
      "private_replay_s": 9000
    }
  },
  "max_user_message_chars": 2000
}
```

The example above is an observed-contract shape, not a claim that every evaluator uses those values.

## Championship integration

`championship-run` can consume one of three mutually exclusive budget sources:

1. `runtime_contract_profile: "kaggle-host-faq-9000-v1"`
2. an explicit `runtime_contract` object
3. legacy `runtime_budget_by_model`

A runtime safety policy can reserve headroom:

```json
{
  "runtime_policy": {
    "reserve_seconds": 120,
    "reserve_fraction": 0.05
  }
}
```

For championship replay selection the smaller of public/private replay budgets is used after reserve. `plan_runtime_capacity()` separately estimates a time-safe candidate count from measured seconds per candidate and also respects the contract candidate cap.

## Compiler identity

`ModelCompilerRegistry` has no implicit fallback. A compiler implementation must be explicitly registered for an exact `(model_id, runtime_id, compiler_id)` compatibility identity. Tokenizer revision, quantization and tool-surface hash can be included in the compatibility evidence fingerprint.

This avoids silently applying one model's prompt/tool compiler to another model when Gemma/GPT-OSS parsing behavior differs.

## Boundary

These contracts describe controlled benchmark execution only. They do not grant BLACK authority and do not authorize activity outside the benchmark environment.
