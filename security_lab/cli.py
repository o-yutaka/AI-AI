from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from research_bundle.canonical import bundle_sha256, canonical_json
from research_bundle.models import SecurityResearchBundle

from .budget import allocate_budget
from .candidate_pack import CandidateRecord, package_candidates
from .competition import KaggleAgentSecurityAdapter
from .compute import ComputeRequest, ComputeTarget, select_compute_target
from .dataset import freeze_dataset
from .kaggle_remote import KaggleRemoteJob, KaggleRemoteRunner, KaggleRunMode
from .manifest import ExperimentManifest
from .research_plan import build_research_plan


def main() -> int:
    parser = argparse.ArgumentParser(prog="kaggle-security-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-bundle")
    verify.add_argument("path")
    canonicalize = subparsers.add_parser("canonicalize-bundle")
    canonicalize.add_argument("path")
    fingerprint = subparsers.add_parser("fingerprint-manifest")
    fingerprint.add_argument("path")
    compute = subparsers.add_parser("select-compute")
    compute.add_argument("path", help="JSON containing request and targets")
    freeze = subparsers.add_parser("freeze-dataset")
    freeze.add_argument(
        "path",
        help="JSON containing dataset_id, source_revision, instance_ids",
    )
    budget = subparsers.add_parser("plan-budget")
    budget.add_argument("total_units", type=float)
    package = subparsers.add_parser("package-candidates")
    package.add_argument("path", help="JSON array of candidate records")
    research = subparsers.add_parser("plan-research")
    research.add_argument("path", help="JSON research-plan specification")

    remote = subparsers.add_parser("kaggle-remote")
    remote.add_argument("notebook_ref", help="Kaggle notebook as owner/slug")
    remote.add_argument("--output-dir", required=True)
    remote.add_argument("--cache-dir", default=".kaggle-lab")
    remote.add_argument("--workspace-dir")
    remote.add_argument(
        "--mode",
        choices=[item.value for item in KaggleRunMode],
        default=KaggleRunMode.REUSE_ONLY.value,
        help="reuse-only never executes; cpu/gpu require explicit opt-in",
    )
    remote.add_argument("--timeout-seconds", type=float, default=15 * 60)
    remote.add_argument("--poll-seconds", type=float, default=5.0)

    args = parser.parse_args()
    if args.command in {"verify-bundle", "canonicalize-bundle"}:
        bundle = _load_bundle(Path(args.path))
        if args.command == "verify-bundle":
            print(
                json.dumps(
                    {
                        "schema_version": bundle.schema_version,
                        "sha256": bundle_sha256(bundle),
                    },
                    sort_keys=True,
                )
            )
        else:
            print(canonical_json(bundle))
        return 0
    if args.command == "fingerprint-manifest":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        manifest = ExperimentManifest(**raw)
        print(
            json.dumps(
                {
                    "experiment_id": manifest.experiment_id,
                    "fingerprint": manifest.fingerprint(),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "select-compute":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        request = ComputeRequest(**raw["request"])
        targets = [ComputeTarget(**item) for item in raw["targets"]]
        selected = select_compute_target(request, targets)
        print(json.dumps({"selected": selected.name}, sort_keys=True))
        return 0
    if args.command == "freeze-dataset":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        frozen = freeze_dataset(
            raw["dataset_id"],
            raw["source_revision"],
            raw["instance_ids"],
        )
        print(
            json.dumps(
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
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "plan-budget":
        print(json.dumps(asdict(allocate_budget(args.total_units)), sort_keys=True))
        return 0
    if args.command == "package-candidates":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        package_result = package_candidates(CandidateRecord(**item) for item in raw)
        print(
            json.dumps(
                {
                    "package_id": package_result.package_id,
                    "canonical_sha256": package_result.canonical_sha256,
                    "candidate_ids": [item.candidate_id for item in package_result.records],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "plan-research":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        competition = KaggleAgentSecurityAdapter().normalize(raw["competition"])
        plan = build_research_plan(
            competition=competition,
            dataset_id=raw["dataset_id"],
            source_revision=raw["source_revision"],
            instance_ids=raw["instance_ids"],
            total_budget_units=float(raw["total_budget_units"]),
            model_ids=raw["model_ids"],
            runtime_ids=raw["runtime_ids"],
            compiler_ids=raw["compiler_ids"],
            quantizations=raw["quantizations"],
        )
        print(
            json.dumps(
                {
                    "plan_id": plan.plan_id,
                    "canonical_sha256": plan.canonical_sha256,
                    "dataset_manifest_sha256": plan.dataset.manifest_sha256,
                    "runtime_variants": len(plan.runtime_matrix.variants),
                    "budget": asdict(plan.budget),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "kaggle-remote":
        result = KaggleRemoteRunner().run(
            KaggleRemoteJob(
                notebook_ref=args.notebook_ref,
                output_dir=Path(args.output_dir),
                cache_dir=Path(args.cache_dir),
                workspace_dir=(Path(args.workspace_dir) if args.workspace_dir else None),
                mode=KaggleRunMode(args.mode),
                timeout_seconds=args.timeout_seconds,
                poll_seconds=args.poll_seconds,
            )
        )
        print(
            json.dumps(
                {
                    "notebook_ref": result.notebook_ref,
                    "job_fingerprint": result.job_fingerprint,
                    "output_dir": str(result.output_dir),
                    "output_sha256": result.output_sha256,
                    "source": result.source,
                    "executed": result.executed,
                    "verified_fingerprint": result.verified_fingerprint,
                },
                sort_keys=True,
            )
        )
        return 0
    return 2


def _load_bundle(path: Path) -> SecurityResearchBundle:
    return SecurityResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
