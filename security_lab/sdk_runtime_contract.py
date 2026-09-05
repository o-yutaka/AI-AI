from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from math import floor
from typing import Any


class RuntimePhase(StrEnum):
    ATTACK_GENERATION = "attack_generation"
    PUBLIC_REPLAY = "public_replay"
    PRIVATE_REPLAY = "private_replay"


class SdkRunSignature(StrEnum):
    UNKNOWN = "UNKNOWN"
    ENV_ONLY = "ENV_ONLY"
    ENV_AND_RUN_CONFIG = "ENV_AND_RUN_CONFIG"


class ContractEvidenceTier(StrEnum):
    HOST_OFFICIAL = "HOST_OFFICIAL"
    COMPETITION_PAGE = "COMPETITION_PAGE"
    SDK_OBSERVED = "SDK_OBSERVED"
    USER_SUPPLIED = "USER_SUPPLIED"


@dataclass(frozen=True)
class ModelPhaseBudgets:
    attack_generation_s: float
    public_replay_s: float
    private_replay_s: float

    def __post_init__(self) -> None:
        for value in (
            self.attack_generation_s,
            self.public_replay_s,
            self.private_replay_s,
        ):
            if value <= 0:
                raise ValueError("all model phase budgets must be positive")

    def for_phase(self, phase: RuntimePhase) -> float:
        return {
            RuntimePhase.ATTACK_GENERATION: self.attack_generation_s,
            RuntimePhase.PUBLIC_REPLAY: self.public_replay_s,
            RuntimePhase.PRIVATE_REPLAY: self.private_replay_s,
        }[phase]


@dataclass(frozen=True)
class CompetitionRuntimeContract:
    contract_id: str
    evidence_tier: ContractEvidenceTier
    source_ref: str
    model_phase_budgets: dict[str, ModelPhaseBudgets]
    sdk_version: str | None = None
    run_signature: SdkRunSignature = SdkRunSignature.UNKNOWN
    global_runtime_limit_s: float | None = None
    max_candidates: int | None = None
    max_messages_per_candidate: int | None = None
    max_tool_hops_per_interact: int | None = None
    max_user_message_chars: int | None = None

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise ValueError("contract_id must be non-empty")
        if not self.source_ref:
            raise ValueError("source_ref must be non-empty")
        if not self.model_phase_budgets:
            raise ValueError("runtime contract requires at least one model budget")
        if self.global_runtime_limit_s is not None and self.global_runtime_limit_s <= 0:
            raise ValueError("global_runtime_limit_s must be positive when provided")
        for name, value in (
            ("max_candidates", self.max_candidates),
            ("max_messages_per_candidate", self.max_messages_per_candidate),
            ("max_tool_hops_per_interact", self.max_tool_hops_per_interact),
            ("max_user_message_chars", self.max_user_message_chars),
        ):
            if value is not None and value < 1:
                raise ValueError(f"{name} must be positive when provided")

    def phase_budget(self, model_id: str, phase: RuntimePhase) -> float:
        try:
            budgets = self.model_phase_budgets[model_id]
        except KeyError as exc:
            raise ValueError(f"runtime contract has no budget for model: {model_id}") from exc
        return budgets.for_phase(phase)

    def fingerprint(self) -> str:
        payload = _canonical_contract_payload(self)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CandidateShape:
    user_message_chars: tuple[int, ...]
    tool_hops_per_interact: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if any(value < 0 for value in self.user_message_chars):
            raise ValueError("user message character counts must be non-negative")
        if any(value < 0 for value in self.tool_hops_per_interact):
            raise ValueError("tool hop counts must be non-negative")


@dataclass(frozen=True)
class RuntimeCapacityPlan:
    model_id: str
    phase: RuntimePhase
    gross_budget_s: float
    reserve_s: float
    usable_budget_s: float
    expected_seconds_per_candidate: float
    max_candidates_by_time: int
    max_candidates_after_contract_cap: int


def kaggle_host_faq_contract() -> CompetitionRuntimeContract:
    """Host-posted evaluator contract from the competition FAQ update.

    The host clarified 9,000 seconds per evaluation phase, 15-hour global runtime,
    2,000 candidates, 32 messages, and 8 tool hops. The FAQ did not settle every
    SDK-level discrepancy, so run signature and message-character limit stay unknown.
    """

    budgets = ModelPhaseBudgets(9_000.0, 9_000.0, 9_000.0)
    return CompetitionRuntimeContract(
        contract_id="kaggle-host-faq-9000-v1",
        evidence_tier=ContractEvidenceTier.HOST_OFFICIAL,
        source_ref="kaggle-discussion-712642",
        model_phase_budgets={
            "gpt_oss": budgets,
            "gemma": budgets,
        },
        global_runtime_limit_s=54_000.0,
        max_candidates=2_000,
        max_messages_per_candidate=32,
        max_tool_hops_per_interact=8,
    )


def validate_candidate_shapes(
    contract: CompetitionRuntimeContract,
    candidates: tuple[CandidateShape, ...],
) -> None:
    if contract.max_candidates is not None and len(candidates) > contract.max_candidates:
        raise ValueError(
            f"candidate count exceeds contract: {len(candidates)} > {contract.max_candidates}"
        )
    for index, candidate in enumerate(candidates):
        if (
            contract.max_messages_per_candidate is not None
            and len(candidate.user_message_chars) > contract.max_messages_per_candidate
        ):
            raise ValueError(
                "candidate message count exceeds contract: "
                f"candidate={index} count={len(candidate.user_message_chars)} "
                f"limit={contract.max_messages_per_candidate}"
            )
        if contract.max_user_message_chars is not None:
            oversized = [
                size
                for size in candidate.user_message_chars
                if size > contract.max_user_message_chars
            ]
            if oversized:
                raise ValueError(
                    "candidate user message exceeds contract character limit: "
                    f"candidate={index} max={max(oversized)} "
                    f"limit={contract.max_user_message_chars}"
                )
        if contract.max_tool_hops_per_interact is not None:
            excessive_hops = [
                hops
                for hops in candidate.tool_hops_per_interact
                if hops > contract.max_tool_hops_per_interact
            ]
            if excessive_hops:
                raise ValueError(
                    "candidate tool hops exceed contract: "
                    f"candidate={index} max={max(excessive_hops)} "
                    f"limit={contract.max_tool_hops_per_interact}"
                )


def plan_runtime_capacity(
    contract: CompetitionRuntimeContract,
    *,
    model_id: str,
    phase: RuntimePhase,
    expected_seconds_per_candidate: float,
    reserve_seconds: float = 0.0,
    reserve_fraction: float = 0.0,
) -> RuntimeCapacityPlan:
    if expected_seconds_per_candidate <= 0:
        raise ValueError("expected_seconds_per_candidate must be positive")
    if reserve_seconds < 0:
        raise ValueError("reserve_seconds must be non-negative")
    if not 0.0 <= reserve_fraction < 1.0:
        raise ValueError("reserve_fraction must be in [0, 1)")

    gross = contract.phase_budget(model_id, phase)
    reserve = max(reserve_seconds, gross * reserve_fraction)
    usable = max(0.0, gross - reserve)
    by_time = floor(usable / expected_seconds_per_candidate)
    capped = by_time
    if contract.max_candidates is not None:
        capped = min(capped, contract.max_candidates)

    return RuntimeCapacityPlan(
        model_id=model_id,
        phase=phase,
        gross_budget_s=gross,
        reserve_s=reserve,
        usable_budget_s=usable,
        expected_seconds_per_candidate=expected_seconds_per_candidate,
        max_candidates_by_time=by_time,
        max_candidates_after_contract_cap=capped,
    )


def championship_replay_budgets(
    contract: CompetitionRuntimeContract,
    *,
    model_ids: tuple[str, ...],
    reserve_seconds: float = 0.0,
    reserve_fraction: float = 0.0,
) -> dict[str, float]:
    """Return conservative replay budgets for championship selection.

    A championship candidate must fit both public and private replay. We therefore
    use the smaller replay-phase budget after the configured safety reserve.
    """

    if reserve_seconds < 0:
        raise ValueError("reserve_seconds must be non-negative")
    if not 0.0 <= reserve_fraction < 1.0:
        raise ValueError("reserve_fraction must be in [0, 1)")

    resolved: dict[str, float] = {}
    for model_id in sorted(set(model_ids)):
        public = contract.phase_budget(model_id, RuntimePhase.PUBLIC_REPLAY)
        private = contract.phase_budget(model_id, RuntimePhase.PRIVATE_REPLAY)
        gross = min(public, private)
        reserve = max(reserve_seconds, gross * reserve_fraction)
        resolved[model_id] = max(0.0, gross - reserve)
    return resolved


def runtime_contract_from_mapping(raw: dict[str, Any]) -> CompetitionRuntimeContract:
    budgets_raw = _dict(raw["model_phase_budgets"])
    budgets = {
        str(model_id): ModelPhaseBudgets(
            attack_generation_s=float(_dict(value)["attack_generation_s"]),
            public_replay_s=float(_dict(value)["public_replay_s"]),
            private_replay_s=float(_dict(value)["private_replay_s"]),
        )
        for model_id, value in budgets_raw.items()
    }
    return CompetitionRuntimeContract(
        contract_id=str(raw["contract_id"]),
        evidence_tier=ContractEvidenceTier(str(raw["evidence_tier"])),
        source_ref=str(raw["source_ref"]),
        model_phase_budgets=budgets,
        sdk_version=_optional_str(raw.get("sdk_version")),
        run_signature=SdkRunSignature(str(raw.get("run_signature", "UNKNOWN"))),
        global_runtime_limit_s=_optional_float(raw.get("global_runtime_limit_s")),
        max_candidates=_optional_int(raw.get("max_candidates")),
        max_messages_per_candidate=_optional_int(raw.get("max_messages_per_candidate")),
        max_tool_hops_per_interact=_optional_int(raw.get("max_tool_hops_per_interact")),
        max_user_message_chars=_optional_int(raw.get("max_user_message_chars")),
    )


def runtime_contract_payload(contract: CompetitionRuntimeContract) -> dict[str, Any]:
    payload = asdict(contract)
    payload["evidence_tier"] = contract.evidence_tier.value
    payload["run_signature"] = contract.run_signature.value
    payload["fingerprint"] = contract.fingerprint()
    return payload


def _canonical_contract_payload(contract: CompetitionRuntimeContract) -> str:
    payload = asdict(contract)
    payload["evidence_tier"] = contract.evidence_tier.value
    payload["run_signature"] = contract.run_signature.value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)
