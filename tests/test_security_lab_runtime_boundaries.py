from security_lab.competition import KaggleAgentSecurityAdapter
from security_lab.compiler import GenericChatCompiler
from security_lab.compute import ComputeRequest, ComputeTarget, select_compute_target
from security_lab.manifest import ExperimentManifest
from security_lab.reproducibility import stable_hash


def test_competition_adapter_normalizes_without_sdk_dependency():
    spec = KaggleAgentSecurityAdapter().normalize({"evaluator_version": "v1", "tool_schema": {"x": {}}})
    assert spec.platform == "kaggle"
    assert spec.internet_enabled is False


def test_generic_compiler_is_deterministic():
    compiler = GenericChatCompiler()
    a = compiler.compile(model_id="m", prompt="p", tool_schema={"t": {}})
    b = compiler.compile(model_id="m", prompt="p", tool_schema={"t": {}})
    assert a.fingerprint == b.fingerprint


def test_manifest_fingerprint_changes_with_runtime_identity():
    base = dict(experiment_id="e", competition_slug="c", model_id="m", compiler_id="x", split="DEV", seed=1,
                tool_surface_hash="a", evaluator_hash="b", dataset_hash="c")
    assert ExperimentManifest(runtime_id="r1", **base).fingerprint() != ExperimentManifest(runtime_id="r2", **base).fingerprint()


def test_compute_selector_respects_vram_and_quota():
    selected = select_compute_target(
        ComputeRequest(required_vram_gb=10, estimated_minutes=30),
        [ComputeTarget("small", True, 8, 100, 0), ComputeTarget("fit", True, 12, 60, 1)],
    )
    assert selected.name == "fit"


def test_stable_hash_ignores_mapping_order():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})
