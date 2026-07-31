from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from string import Formatter
from typing import Any, Literal, Protocol
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from .models import CandidateAction
from .security import find_sensitive_paths, redact_value


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
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("base_url must be an absolute http or https URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("base_url must not contain credentials, query, or fragment")
        if parsed.scheme == "http" and not self.allow_insecure_http:
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


def _read_bounded_response(response: httpx.Response, maximum: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > maximum:
            raise ToolExecutionError("HTTP tool response exceeded configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


class HttpJsonToolAdapter:
    """Execute only preconfigured HTTP operations against one fixed base URL.

    The model may provide non-sensitive payload values, but it cannot choose a host,
    HTTP method, arbitrary path, redirect target, or secret. Responses are bounded
    while streaming, before the complete body is loaded into memory.
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

    @property
    def operations(self) -> frozenset[str]:
        return frozenset(self._config.operations)

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

        sensitive_paths = find_sensitive_paths(action.payload)
        if sensitive_paths:
            raise ToolExecutionError(
                "sensitive values must be referenced indirectly, not sent in action payload: "
                + ", ".join(sensitive_paths)
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
            ) as client, client.stream(
                operation.method,
                url,
                headers=headers,
                **request_kwargs,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                content = _read_bounded_response(
                    response,
                    self._config.max_response_bytes,
                )
                status_code = response.status_code
                encoding = response.encoding or "utf-8"
        except ToolExecutionError:
            raise
        except httpx.HTTPError as exc:
            raise ToolExecutionError(f"HTTP tool request failed: {exc}") from exc

        if "json" in content_type:
            try:
                parsed: Any = json.loads(content.decode(encoding))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ToolExecutionError("HTTP tool returned malformed JSON") from exc
        else:
            parsed = content.decode(encoding, errors="replace")

        return {
            "executed": True,
            "adapter": "http_json",
            "tool": action.tool,
            "operation": action.operation,
            "status_code": status_code,
            "response": redact_value(parsed),
        }


class ToolRegistryExecutor:
    """Resolve an action to an explicitly registered adapter by exact tool name."""

    def __init__(self, adapters: Mapping[str, ToolAdapter]) -> None:
        if not adapters:
            raise ValueError("at least one tool adapter is required")
        self._adapters = dict(adapters)

    @property
    def capabilities(self) -> frozenset[tuple[str, str]]:
        declared: set[tuple[str, str]] = set()
        for tool_name, adapter in self._adapters.items():
            operations = getattr(adapter, "operations", frozenset())
            declared.update((tool_name, operation) for operation in operations)
        return frozenset(declared)

    def supports(self, action: CandidateAction) -> bool:
        return (action.tool, action.operation) in self.capabilities

    def __call__(self, action: CandidateAction) -> dict[str, Any]:
        adapter = self._adapters.get(action.tool)
        if adapter is None:
            raise ToolExecutionError(f"tool is not registered: {action.tool}")
        return adapter.execute(action)


def tool_executor_from_environment() -> ToolRegistryExecutor | None:
    """Build HTTP adapters from TOOL_ADAPTERS_JSON when explicitly configured."""

    raw = os.getenv("TOOL_ADAPTERS_JSON")
    if not raw:
        return None
    try:
        decoded = json.loads(raw)
        configs = TypeAdapter(dict[str, HttpToolConfig]).validate_python(decoded)
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"invalid TOOL_ADAPTERS_JSON: {exc}") from exc

    return ToolRegistryExecutor(
        {name: HttpJsonToolAdapter(config) for name, config in configs.items()}
    )
