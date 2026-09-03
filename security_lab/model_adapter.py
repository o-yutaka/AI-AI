from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CompiledPrompt:
    model_family: str
    rendered_prompt: str
    compiler_version: str
    metadata: dict[str, str]


class ModelCompiler(Protocol):
    """Translate a model-neutral research prompt into one model-family surface.

    The compiler owns formatting only. It does not decide whether a research
    hypothesis is valid and it cannot mint evaluation or adoption authority.
    """

    model_family: str
    compiler_version: str

    def compile(self, instruction: str, *, tool_schema: str | None = None) -> CompiledPrompt: ...


@dataclass(frozen=True)
class PlainTextCompiler:
    model_family: str = "generic"
    compiler_version: str = "0.1"

    def compile(self, instruction: str, *, tool_schema: str | None = None) -> CompiledPrompt:
        rendered = instruction.strip()
        if tool_schema:
            rendered = f"{rendered}\n\n<tool-schema>\n{tool_schema.strip()}\n</tool-schema>"
        return CompiledPrompt(
            model_family=self.model_family,
            rendered_prompt=rendered,
            compiler_version=self.compiler_version,
            metadata={"tool_schema_included": str(bool(tool_schema)).lower()},
        )
