from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CompetitionSpec:
    platform: str
    slug: str
    name: str
    evaluator_version: str
    tool_schema: Mapping[str, Any]
    time_budget_seconds: int | None = None
    internet_enabled: bool = False


class CompetitionAdapter(Protocol):
    def normalize(self, raw: Mapping[str, Any]) -> CompetitionSpec: ...


class KaggleAgentSecurityAdapter:
    """Normalize competition metadata without coupling the lab to Kaggle SDKs."""

    def normalize(self, raw: Mapping[str, Any]) -> CompetitionSpec:
        slug = str(raw.get("slug", "ai-agent-security-multi-step-tool-attacks"))
        name = str(raw.get("name", "AI Agent Security - Multi-Step Tool Attacks"))
        version = str(raw.get("evaluator_version", "unknown"))
        tools = raw.get("tool_schema", {})
        if not isinstance(tools, Mapping):
            raise TypeError("tool_schema must be a mapping")
        budget = raw.get("time_budget_seconds")
        return CompetitionSpec(
            platform="kaggle",
            slug=slug,
            name=name,
            evaluator_version=version,
            tool_schema=dict(tools),
            time_budget_seconds=int(budget) if budget is not None else None,
            internet_enabled=bool(raw.get("internet_enabled", False)),
        )
