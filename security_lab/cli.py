from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_bundle.canonical import bundle_sha256, canonical_json
from research_bundle.models import SecurityResearchBundle
from .compute import ComputeRequest, ComputeTarget, select_compute_target
from .manifest import ExperimentManifest


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

    args = parser.parse_args()
    if args.command in {"verify-bundle", "canonicalize-bundle"}:
        bundle = _load_bundle(Path(args.path))
        if args.command == "verify-bundle":
            print(json.dumps({"schema_version": bundle.schema_version, "sha256": bundle_sha256(bundle)}, sort_keys=True))
        else:
            print(canonical_json(bundle))
        return 0
    if args.command == "fingerprint-manifest":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        manifest = ExperimentManifest(**raw)
        print(json.dumps({"experiment_id": manifest.experiment_id, "fingerprint": manifest.fingerprint()}, sort_keys=True))
        return 0
    if args.command == "select-compute":
        raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
        request = ComputeRequest(**raw["request"])
        targets = [ComputeTarget(**item) for item in raw["targets"]]
        selected = select_compute_target(request, targets)
        print(json.dumps({"selected": selected.name}, sort_keys=True))
        return 0
    return 2


def _load_bundle(path: Path) -> SecurityResearchBundle:
    return SecurityResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
