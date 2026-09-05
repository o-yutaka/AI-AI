import pytest

from security_lab.compiler import GenericChatCompiler
from security_lab.compiler_registry import CompilerCompatibility, ModelCompilerRegistry


def test_compiler_registry_requires_exact_runtime_binding() -> None:
    registry = ModelCompilerRegistry()
    compatibility = CompilerCompatibility(
        model_id="gpt_oss",
        runtime_id="target-runtime",
        compiler_id="generic-chat.v1",
        source_ref="recorded-runtime-test",
        tokenizer_revision="rev-a",
    )
    registry.register(compatibility, GenericChatCompiler())

    compiled = registry.compile_bound(
        model_id="gpt_oss",
        runtime_id="target-runtime",
        compiler_id="generic-chat.v1",
        prompt="synthetic benchmark prompt",
        tool_schema={"type": "function"},
    )
    assert compiled.model_id == "gpt_oss"
    assert compiled.compiler_id == "generic-chat.v1"

    with pytest.raises(ValueError, match="no exact compiler compatibility binding"):
        registry.compile_bound(
            model_id="gemma",
            runtime_id="target-runtime",
            compiler_id="generic-chat.v1",
            prompt="synthetic benchmark prompt",
            tool_schema={"type": "function"},
        )


def test_compiler_registry_rejects_implementation_identity_mismatch() -> None:
    registry = ModelCompilerRegistry()
    compatibility = CompilerCompatibility(
        model_id="gpt_oss",
        runtime_id="target-runtime",
        compiler_id="different-compiler.v1",
        source_ref="test",
    )
    with pytest.raises(ValueError, match="implementation id"):
        registry.register(compatibility, GenericChatCompiler())


def test_compatibility_fingerprint_changes_on_tokenizer_or_runtime_change() -> None:
    first = CompilerCompatibility(
        model_id="gpt_oss",
        runtime_id="runtime-a",
        compiler_id="generic-chat.v1",
        source_ref="test",
        tokenizer_revision="tok-a",
    )
    second = CompilerCompatibility(
        model_id="gpt_oss",
        runtime_id="runtime-a",
        compiler_id="generic-chat.v1",
        source_ref="test",
        tokenizer_revision="tok-b",
    )
    third = CompilerCompatibility(
        model_id="gpt_oss",
        runtime_id="runtime-b",
        compiler_id="generic-chat.v1",
        source_ref="test",
        tokenizer_revision="tok-a",
    )
    assert first.fingerprint() != second.fingerprint()
    assert first.fingerprint() != third.fingerprint()
