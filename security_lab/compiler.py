from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CompiledRequest:
    compiler_id: str
    model_id: str
    payload: Mapping[str, Any]
    fingerprint: str


class ModelCompiler(Protocol):
    compiler_id: str

    def compile(
        self,
        *,
        model_id: str,
        prompt: str,
        tool_schema: Mapping[str, Any],
    ) -> CompiledRequest: ...


class GenericChatCompiler:
    compiler_id = "generic-chat.v1"

    def compile(
        self,
        *,
        model_id: str,
        prompt: str,
        tool_schema: Mapping[str, Any],
    ) -> CompiledRequest:
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
            "tools": tool_schema,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return CompiledRequest(self.compiler_id, model_id, payload, fingerprint)
