from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import SecurityResearchBundle, SecurityResearchBundleV2

ResearchBundle = SecurityResearchBundle | SecurityResearchBundleV2


def canonical_payload(bundle: ResearchBundle) -> dict[str, Any]:
    return bundle.model_dump(mode="json", exclude_none=True)


def canonical_json(bundle: ResearchBundle) -> str:
    return json.dumps(
        canonical_payload(bundle),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def bundle_sha256(bundle: ResearchBundle) -> str:
    return hashlib.sha256(canonical_json(bundle).encode("utf-8")).hexdigest()


def export_bundle(bundle: ResearchBundle, destination: str | Path) -> tuple[Path, str]:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical_json(bundle) + "\n"
    path.write_text(content, encoding="utf-8")
    return path, hashlib.sha256(content.encode("utf-8")).hexdigest()
