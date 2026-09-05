from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from .compiler import CompiledRequest, ModelCompiler


@dataclass(frozen=True)
class CompilerCompatibility:
    model_id: str
    runtime_id: str
    compiler_id: str
    source_ref: str
    quantization: str | None = None
    tokenizer_revision: str | None = None
    tool_surface_hash: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("model_id", self.model_id),
            ("runtime_id", self.runtime_id),
            ("compiler_id", self.compiler_id),
            ("source_ref", self.source_ref),
        ):
            if not value:
                raise ValueError(f"{name} must be non-empty")

    def fingerprint(self) -> str:
        payload = json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CompilerKey:
    model_id: str
    runtime_id: str
    compiler_id: str


class ModelCompilerRegistry:
    """Explicit model/runtime/compiler registry with no implicit fallback.

    Competition runtimes can differ in prompt formatting and tool-call parsing. A
    compiler must therefore be deliberately bound to an observed compatibility
    identity rather than silently reusing a generic compiler for an unknown target.
    """

    def __init__(self) -> None:
        self._entries: dict[CompilerKey, tuple[CompilerCompatibility, ModelCompiler]] = {}

    def register(
        self,
        compatibility: CompilerCompatibility,
        compiler: ModelCompiler,
    ) -> None:
        if compiler.compiler_id != compatibility.compiler_id:
            raise ValueError(
                "compiler implementation id does not match compatibility binding"
            )
        key = CompilerKey(
            compatibility.model_id,
            compatibility.runtime_id,
            compatibility.compiler_id,
        )
        if key in self._entries:
            raise ValueError(f"compiler binding already registered: {key}")
        self._entries[key] = (compatibility, compiler)

    def resolve(
        self,
        *,
        model_id: str,
        runtime_id: str,
        compiler_id: str,
    ) -> tuple[CompilerCompatibility, ModelCompiler]:
        key = CompilerKey(model_id, runtime_id, compiler_id)
        try:
            return self._entries[key]
        except KeyError as exc:
            raise ValueError(
                "no exact compiler compatibility binding for "
                f"model={model_id} runtime={runtime_id} compiler={compiler_id}"
            ) from exc

    def compile_bound(
        self,
        *,
        model_id: str,
        runtime_id: str,
        compiler_id: str,
        prompt: str,
        tool_schema: Mapping[str, Any],
    ) -> CompiledRequest:
        compatibility, compiler = self.resolve(
            model_id=model_id,
            runtime_id=runtime_id,
            compiler_id=compiler_id,
        )
        compiled = compiler.compile(
            model_id=model_id,
            prompt=prompt,
            tool_schema=tool_schema,
        )
        if compiled.compiler_id != compatibility.compiler_id:
            raise ValueError("compiled request changed compiler identity")
        if compiled.model_id != compatibility.model_id:
            raise ValueError("compiled request changed model identity")
        return compiled

    def compatibility_fingerprint(
        self,
        *,
        model_id: str,
        runtime_id: str,
        compiler_id: str,
    ) -> str:
        compatibility, _ = self.resolve(
            model_id=model_id,
            runtime_id=runtime_id,
            compiler_id=compiler_id,
        )
        return compatibility.fingerprint()
