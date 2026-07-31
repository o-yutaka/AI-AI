from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from string import Formatter
from typing import Any, Literal, Protocol
from urllib.parse import quote

import httpx
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from .models import CandidateAction


class ToolExecutionError(RuntimeError):
    """Raised when a configured tool cannot be executed safely."""


class ToolAdapter(Protocol):
    def execute(self, action: CandidateAction) -> dict[str, Any]: ...


class HttpOperation(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    path: str = Field(min_length=1, max_length=500)
    payload_mode: Literal["json", "query", "none"] = "json"

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("operation path must start with /")
        if "://" in value or ".." in value:
            raise ValueError("operation path must be relative and traversal-free")
        return value


class HttpToolConfig(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    operations: dict[str, HttpOperation] = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    max_response_bytes: int = Field(default=262_144, ge=1_024, le=5_242_880)
    allow_insecure_http: bool = False

    @model_validator(mode="after")
    def validate_base_url(self) -> HttpToolConfig:
        if not self.base_url.startswith(("https://", "http://")):
            raise ValueError("base_url must use http or https")
        if self.base_url.startswith("http://") and not self.allow_insecure_http:
            raise ValueError("plain HTTP requires allow_insecure_http=true")
        return self


_ENV_PATTERN = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _expand_environment(value: str, environment: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        resolved = environment.get(name)
        if resolved is None:
            raise ToolExecutionError(f"missing environment variable: {name}")
        return resolved

    return _ENV_PATTERN.sub(replace, value)


class HttpJsonToolAdapter:
    """Execute only preconfigured HTTP operations against one fixed base URL.

    The model may provide payload values, but it cannot choose a host, HTTP method, or
    arbitrary path. Redirects are disabled and response size is bounded.
    """

    def __init__(
        self,
        config: HttpToolConfig,
        *,
        environment: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._environment = environment if environment is not None else os.environ
        self._transport = transport

    @staticmethod
    def _render_path(template: str, payload: Mapping[str, Any]) -> str:
        values: dict[str, str] = {}
        for _, field_name, _, _ in Formatter().parse(template):
            if not field_name:
                continue
            if field_name not in payload:
                raise ToolExecutionError(f"missing path payload field: {field_name}")
            value = payload[field_name]
            if isinstance(value, (dict, list, tuple, set)):
                raise ToolExecutionError(f"path payload field must be scalar: {field_name}")
            values[field_name] = quote(str(value), safe="")
        try:
            rendered = template.format_map(values)
        except (KeyError, ValueError) as exc:
            raise ToolExecutionError(f"invalid operation path template: {exc}") from exc
        if ".." in rendered or "://" in rendered:
            raise ToolExecutionError("rendered path violated adapter boundary")
        return rendered

    def execute(self, action: CandidateAction) -> dict[str, Any]:
        operation = self._config.operations.get(action.operation)
        if operation is None:
            raise ToolExecutionError(
                f"operation is not configured for tool {action.tool}: {action.operation}"
            )

        path = self._render_path(operation.path, action.payload)
        url = f"{self._config.base_url.rstrip('/')}{path}"
        headers = {
            name: _expand_environment(value, self._environment)
            for name, value in self._config.headers.items()
        }
        request_kwargs: dict[str, Any] = {}
        if operation.payload_mode == "json":
            request_kwargs["json"] = action.payload
        elif operation.payload_mode == "query":
            request_kwargs["params"] = action.payload

        try:
            with httpx.Client(
                timeout=self._config.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = client.request(
                    operation.method,
                    url,
                    headers=headers,
                    **request_kwargs,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"HTTP tool request failed: {exc}") from exc

        content = response.content
        if len(content) > self._config.max_response_bytes:
            raise ToolExecutionError("HTTP tool response exceeded configured size limit")

        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            try:
                parsed: Any = response.json()
            except ValueError as exc:
                raise ToolExecutionError("HTTP tool returned malformed JSON") from exc
        else:
            parsed = response.text

        return {
            "executed": True,
            "adapter": "http_json",
            "tool": action.tool,
            "operation": action.operation,
            "status_code": response.status_code,
            "response": parsed,
        }


class ToolRegistryExecutor:
    """Resolve an action to an explicitly registered adapter by exact tool name."""

    def __init__(self, adapters: Mapping[str, ToolAdapter]) -> None:
        if not adapters:
            raise ValueError("at least one tool adapter is required")
        self._adapters = dict(adapters)

    def __call__(self, action: CandidateAction) -> dict[str, Any]:
        adapter = self._adapters.get(action.tool)
        if adapter is None:
            raise ToolExecutionError(f"tool is not registered: {action.tool}")
        return adapter.execute(action)


def tool_executor_from_environment() -> ToolRegistryExecutor | None:
    """Build HTTP adapters from TOOL_ADAPTERS_JSON when explicitly configured.

    Example shape:
    {
      "support_api": {
        "base_url": "https://api.example.com",
        "headers": {"Authorization": "Bearer ${SUPPORT_API_TOKEN}"},
        "operations": {
          "reply": {"method": "POST", "path": "/tickets/{ticket_id}/reply"}
        }
      }
    }
    """

    raw = os.getenv("TOOL_ADAPTERS_JSON")
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
        configs = TypeAdapter(dict[str, HttpToolConfig]).validate_python(decoded)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"invalid TOOL_ADAPTERS_JSON: {exc}") from exc

    return ToolRegistryExecutor(
        {
            name: HttpJsonToolAdapter(config)
            for name, config in configs.items()
        }
    )
