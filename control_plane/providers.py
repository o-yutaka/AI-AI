from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from .models import ActionContract, CandidateAction
from .security import redact_text


class ProviderError(RuntimeError):
    """Base error for planner/provider failures."""


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an invalid or unsafe planning response."""


class ToolCapability(BaseModel):
    """Tool surface exposed to the model for candidate generation only."""

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=500)
    operations: list[str] = Field(min_length=1, max_length=50)
    input_schema: dict[str, Any] = Field(default_factory=dict)


class PlannedRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    observation: dict[str, Any] = Field(default_factory=dict)
    contract: ActionContract
    tools: list[ToolCapability] = Field(min_length=1, max_length=50)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class PlannerResult(BaseModel):
    provider: str
    model: str
    candidates: list[CandidateAction] = Field(min_length=1, max_length=100)


class CandidatePlanner(Protocol):
    provider_name: str
    model: str

    def plan(self, request: PlannedRunRequest) -> PlannerResult: ...


def _read_bounded_response(response: httpx.Response, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > maximum:
            raise ProviderResponseError(
                "provider response exceeded configured size limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


class OpenAICompatiblePlanner:
    """Generate untrusted action candidates through an OpenAI-compatible endpoint.

    Candidate generation and action execution remain separate. The result still passes
    through the runtime's contract, permission, evidence, sensitive-data, tool-capability,
    ranking, approval, and idempotency gates before any configured adapter can run.
    """

    provider_name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = 524_288,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.startswith(("https://", "http://")):
            raise ValueError("base_url must use http or https")
        if not model.strip():
            raise ValueError("model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 1_024 <= max_response_bytes <= 5_242_880:
            raise ValueError("max_response_bytes must be between 1024 and 5242880")

        self.base_url = normalized
        self.model = model.strip()
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._transport = transport

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You generate candidate actions for an audited agent control plane. "
            "Return one JSON object with a candidates array only. Each candidate must "
            "contain action_id, name, tool, operation, payload, expected_value, risk, "
            "reversible, evidence, and required_permissions. Use only tools and operations "
            "listed in the supplied tool catalog. Do not include credentials, tokens, "
            "passwords, email addresses, phone numbers, or postal addresses in payloads. "
            "Use stable record identifiers instead. Do not claim execution occurred. "
            "High-risk actions need concrete evidence references."
        )

    @staticmethod
    def _user_payload(request: PlannedRunRequest) -> str:
        payload = {
            "goal": request.goal,
            "observation": request.observation,
            "contract": request.contract.model_dump(mode="json"),
            "tool_catalog": [tool.model_dump(mode="json") for tool in request.tools],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _message_content(payload: Mapping[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                "provider response is missing choices[0].message.content"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("provider message content must be a non-empty string")
        return content

    @staticmethod
    def _validate_declared_tools(
        candidates: list[CandidateAction], tools: list[ToolCapability]
    ) -> None:
        declared = {
            (tool.name, operation)
            for tool in tools
            for operation in tool.operations
        }
        undeclared = sorted(
            {
                f"{candidate.tool}.{candidate.operation}"
                for candidate in candidates
                if (candidate.tool, candidate.operation) not in declared
            }
        )
        if undeclared:
            raise ProviderResponseError(
                "provider referenced undeclared tool operations: " + ", ".join(undeclared)
            )

    def plan(self, request: PlannedRunRequest) -> PlannerResult:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_payload(request)},
            ],
        }

        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                ) as response:
                    response.raise_for_status()
                    content = _read_bounded_response(
                        response,
                        self._max_response_bytes,
                    )
                    response_payload = json.loads(
                        content.decode(response.encoding or "utf-8")
                    )
        except ProviderResponseError:
            raise
        except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(
                f"provider request failed: {redact_text(str(exc))}"
            ) from exc

        message_content = self._message_content(response_payload)
        try:
            decoded = json.loads(message_content)
            candidates = [
                CandidateAction.model_validate(candidate)
                for candidate in decoded["candidates"]
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise ProviderResponseError(
                "provider content is not a valid CandidateAction payload"
            ) from exc

        if not candidates:
            raise ProviderResponseError("provider returned no candidates")
        if len(candidates) > 100:
            raise ProviderResponseError("provider returned more than 100 candidates")

        self._validate_declared_tools(candidates, request.tools)
        return PlannerResult(
            provider=self.provider_name,
            model=self.model,
            candidates=candidates,
        )
