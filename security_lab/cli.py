from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from research_bundle.canonical import bundle_sha256, canonical_json
from research_bundle.models import SecurityResearchBundle, SecurityResearchBundleV2

from .budget import allocate_budget
from .candidate_pack import CandidateRecord, package_candidates
from .championship_io import championship_result_payload, run_championship_from_mapping
from .championship_risk_io import (
    risk_championship_result_payload,
    run_risk_championship_from_mapping,
)
from .competition import KaggleAgentSecurityAdapter
from .compute import ComputeRequest, ComputeTarget, select_compute_target
from .dataset import freeze_dataset
from .kaggle_remote import KaggleRemoteRunner, KaggleRemoteSpec, stage_scratch_script
from .manifest import ExperimentManifest
from .research_loop_io import run_research_loop_from_mapping
from .research_plan import build_research_plan
from .winning_io import rank_winning_portfolio_from_mapping, winning_strategy_result_payload


def main() -> int:
    parser = argparse.ArgumentParser(prog="kaggle-security-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    _register_commands(commands)
    args = parser.parse_args()
    return _dispatch(args)


def _register_commands(commands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    _path_command(commands, "verify-bundle")
    _path_command(commands, "canonicalize-bundle")
    _path_command(commands, "fingerprint-manifest")
    _path_command(commands, "select-compute")
    _path_command(commands, "freeze-dataset")
    budget = commands.add_parser("plan-budget")
    budget.add_argument("total_units", type=float)
    _path_command(commands, "package-candidates")
    _path_command(commands, "plan-research")
    _path_command(
        commands,
        "research-run",
        help_text="JSON recorded-evidence research-loop specification",
    )
    _path_command(
        commands,
        "rank-winning-portfolio",
        help_text="JSON winning-strategy evidence specification",
    )
    _path_command(
        commands,
        "championship-run",
        help_text="JSON hard-gated private-objective championship specification",
    )
    _path_command(
        commands,
        "championship-risk-run",
        help_text="JSON scenario-robust championship + atomic replay-wall specification",
    )
    _path_command(commands, "kaggle-stage", help_text="JSON scratch-kernel specification")
    _path_command(commands, "kaggle-run", help_text="JSON remote-run specification")
    status = commands.add_parser("kaggle-status")
    status.add_argument("kernel_ref")
    output = commands.add_parser("kaggle-output")
    output.add_argument("kernel_ref")
    output.add_argument("destination")
    submit = commands.add_parser("kaggle-submit")
    submit.add_argument("path", help="JSON explicit submission specification")


def _path_command(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    *,
    help_text: str | None = None,
) -> None:
    command = commands.add_parser(name)
    command.add_argument("path", help=help_text)


def _dispatch(args: argparse.Namespace) -> int:
    if args.command in {"verify-bundle", "canonicalize-bundle"}:
        return _bundle_command(args.command, Path(args.path))
    if args.command == "fingerprint-manifest":
        raw = _json_object(args.path)
        manifest = ExperimentManifest(**raw)
        _print_json(
            {
                "experiment_id": manifest.experiment_id,
                "fingerprint": manifest.fingerprint(),
            }
        )
        return 0
    if args.command == "select-compute":
        raw = _json_object(args.path)
        selected = select_compute_target(
            ComputeRequest(**_dict(raw["request"])),
            [ComputeTarget(**_dict(item)) for item in _list(raw["targets"])],
        )
        _print_json({"selected": selected.name})
        return 0
    if args.command == "freeze-dataset":
        return _freeze_dataset(args.path)
    if args.command == "plan-budget":
        _print_json(asdict(allocate_budget(args.total_units)))
        return 0
    if args.command == "package-candidates":
        raw = _json_list(args.path)
        result = package_candidates(CandidateRecord(**_dict(item)) for item in raw)
        _print_json(
            {
                "package_id": result.package_id,
                "canonical_sha256": result.canonical_sha256,
                "candidate_ids": [item.candidate_id for item in result.records],
            }
        )
        return 0
    if args.command == "plan-research":
        return _plan_research(args.path)
    if args.command == "research-run":
        return _research_run(args.path)
    if args.command == "rank-winning-portfolio":
        result = rank_winning_portfolio_from_mapping(_json_object(args.path))
        _print_json(winning_strategy_result_payload(result))
        return 0
    if args.command == "championship-run":
        result = run_championship_from_mapping(_json_object(args.path))
        _print_json(championship_result_payload(result))
        return 0
    if args.command == "championship-risk-run":
        result = run_risk_championship_from_mapping(_json_object(args.path))
        _print_json(risk_championship_result_payload(result))
        return 0
    if args.command == "kaggle-stage":
        return _kaggle_stage(args.path)
    if args.command == "kaggle-run":
        return _kaggle_run(args.path)
    if args.command == "kaggle-status":
        _print_json(
            {
                "kernel_ref": args.kernel_ref,
                "status": KaggleRemoteRunner().status(args.kernel_ref),
            }
        )
        return 0
    if args.command == "kaggle-output":
        files = KaggleRemoteRunner().output(args.kernel_ref, args.destination)
        _print_json({"kernel_ref": args.kernel_ref, "output_files": files})
        return 0
    if args.command == "kaggle-submit":
        return _kaggle_submit(args.path)
    return 2


def _bundle_command(command: str, path: Path) -> int:
    bundle = _load_bundle(path)
    if command == "verify-bundle":
        _print_json(
            {
                "schema_version": bundle.schema_version,
                "sha256": bundle_sha256(bundle),
            }
        )
    else:
        print(canonical_json(bundle))
    return 0


def _research_run(path: str) -> int:
    raw = _json_object(path)
    bundle = run_research_loop_from_mapping(raw)
    content = canonical_json(bundle)
    output_path = raw.get("output_path")
    if output_path is None:
        print(content)
        return 0

    destination = Path(str(output_path))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content + "\n", encoding="utf-8")
    _print_json(
        {
            "schema_version": bundle.schema_version,
            "sha256": bundle_sha256(bundle),
            "output_path": str(destination),
            "knowledge_materials": len(bundle.knowledge_materials),
            "research_decisions": len(bundle.research_decisions),
            "environments": len(bundle.environments),
        }
    )
    return 0


def _freeze_dataset(path: str) -> int:
    raw = _json_object(path)
    frozen = freeze_dataset(
        str(raw["dataset_id"]),
        str(raw["source_revision"]),
        [str(item) for item in _list(raw["instance_ids"])],
    )
    _print_json(
        {
            "dataset_id": frozen.dataset_id,
            "source_revision": frozen.source_revision,
            "manifest_sha256": frozen.manifest_sha256,
            "instances": [
                {
                    "instance_id": item.instance_id,
                    "split": item.split.value,
                    "identity_hash": item.identity_hash,
                }
                for item in frozen.instances
            ],
        }
    )
    return 0


def _plan_research(path: str) -> int:
    raw = _json_object(path)
    plan = build_research_plan(
        competition=KaggleAgentSecurityAdapter().normalize(_dict(raw["competition"])),
        dataset_id=str(raw["dataset_id"]),
        source_revision=str(raw["source_revision"]),
        instance_ids=[str(item) for item in _list(raw["instance_ids"])],
        total_budget_units=float(raw["total_budget_units"]),
        model_ids=[str(item) for item in _list(raw["model_ids"])],
        runtime_ids=[str(item) for item in _list(raw["runtime_ids"])],
        compiler_ids=[str(item) for item in _list(raw["compiler_ids"])],
        quantizations=[str(item) for item in _list(raw["quantizations"])],
    )
    _print_json(
        {
            "plan_id": plan.plan_id,
            "canonical_sha256": plan.canonical_sha256,
            "dataset_manifest_sha256": plan.dataset.manifest_sha256,
            "runtime_variants": len(plan.runtime_matrix.variants),
            "budget": asdict(plan.budget),
        }
    )
    return 0


def _kaggle_stage(path: str) -> int:
    raw = _json_object(path)
    source = Path(str(raw["source_file"])).read_text(encoding="utf-8")
    root = stage_scratch_script(
        str(raw["destination"]),
        kernel_ref=str(raw["kernel_ref"]),
        title=str(raw["title"]),
        source=source,
        competition_slug=_optional_str(raw.get("competition_slug")),
        enable_gpu=bool(raw.get("enable_gpu", True)),
        machine_shape=str(raw.get("machine_shape", "NvidiaTeslaT4")),
    )
    _print_json({"staged": str(root)})
    return 0


def _kaggle_run(path: str) -> int:
    raw = _json_object(path)
    result = KaggleRemoteRunner().run(
        KaggleRemoteSpec(
            kernel_ref=str(raw["kernel_ref"]),
            source_dir=Path(str(raw["source_dir"])),
            output_dir=Path(str(raw["output_dir"])),
            poll_seconds=float(raw.get("poll_seconds", 15)),
            timeout_seconds=float(raw.get("timeout_seconds", 54_000)),
        )
    )
    _print_json(
        {
            "kernel_ref": result.kernel_ref,
            "status": result.status,
            "output_dir": str(result.output_dir),
            "output_files": result.output_files,
        }
    )
    return 0


def _kaggle_submit(path: str) -> int:
    raw = _json_object(path)
    version_raw = raw.get("version")
    version = int(version_raw) if version_raw is not None else None
    output = KaggleRemoteRunner().submit(
        competition_slug=str(raw["competition_slug"]),
        kernel_ref=str(raw["kernel_ref"]),
        output_file=str(raw["output_file"]),
        message=str(raw["message"]),
        version=version,
    )
    _print_json({"submitted": True, "response": output})
    return 0


def _json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_object(path: str) -> dict[str, Any]:
    return _dict(_json(path))


def _json_list(path: str) -> list[Any]:
    return _list(_json(path))


def _dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("expected JSON array")
    return value


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _print_json(value: Any) -> None:
    print(json.dumps(value, sort_keys=True))


def _load_bundle(path: Path) -> SecurityResearchBundle | SecurityResearchBundleV2:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("bundle must be a JSON object")
    schema = raw.get("schema_version")
    if schema == "security-research-bundle.v1":
        return SecurityResearchBundle.model_validate(raw)
    if schema == "security-research-bundle.v2":
        return SecurityResearchBundleV2.model_validate(raw)
    raise ValueError(f"unsupported research bundle schema: {schema}")


if __name__ == "__main__":
    raise SystemExit(main())
