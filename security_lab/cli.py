from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_bundle.canonical import bundle_sha256, canonical_json
from research_bundle.models import SecurityResearchBundle


def main() -> int:
    parser = argparse.ArgumentParser(prog="kaggle-security-lab")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-bundle", help="Validate and hash a security-research-bundle.v1 file")
    verify.add_argument("path")

    canonicalize = subparsers.add_parser("canonicalize-bundle", help="Print canonical JSON for a bundle")
    canonicalize.add_argument("path")

    args = parser.parse_args()
    bundle = _load_bundle(Path(args.path))
    if args.command == "verify-bundle":
        print(json.dumps({"schema_version": bundle.schema_version, "sha256": bundle_sha256(bundle)}, sort_keys=True))
        return 0
    if args.command == "canonicalize-bundle":
        print(canonical_json(bundle))
        return 0
    return 2


def _load_bundle(path: Path) -> SecurityResearchBundle:
    return SecurityResearchBundle.model_validate_json(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
