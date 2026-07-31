from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_DEFAULT_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "setcookie",
    "password",
    "passwd",
    "secret",
    "clientsecret",
    "token",
    "accesstoken",
    "refreshtoken",
    "apikey",
    "api-key",
    "email",
    "emailaddress",
    "phone",
    "phonenumber",
    "address",
}

_BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(authorization|cookie|password|secret|token|api[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d ()-]{7,}\d)(?!\w)")


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", value.strip().lower())


def sensitive_keys_from_environment() -> set[str]:
    configured = {
        _normalize_key(item)
        for item in os.getenv("TRACE_REDACTION_KEYS", "").split(",")
        if item.strip()
    }
    return {_normalize_key(item) for item in _DEFAULT_SENSITIVE_KEYS} | configured


def is_sensitive_key(key: str, sensitive_keys: set[str] | None = None) -> bool:
    normalized = _normalize_key(key)
    keys = sensitive_keys or sensitive_keys_from_environment()
    return normalized in keys or any(
        normalized.endswith(candidate)
        for candidate in keys
        if len(candidate) >= 5
    )


def redact_text(text: str) -> str:
    redacted = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    redacted = _ASSIGNMENT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        redacted,
    )
    redacted = _EMAIL_PATTERN.sub(REDACTED, redacted)
    redacted = _PHONE_PATTERN.sub(REDACTED, redacted)
    for name, value in os.environ.items():
        if value and len(value) >= 6 and is_sensitive_key(name):
            redacted = redacted.replace(value, REDACTED)
    return redacted


def find_sensitive_paths(
    value: Any,
    *,
    sensitive_keys: set[str] | None = None,
    prefix: str = "$",
) -> list[str]:
    keys = sensitive_keys or sensitive_keys_from_environment()
    found: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}"
            if is_sensitive_key(key, keys):
                found.append(path)
            else:
                found.extend(
                    find_sensitive_paths(child, sensitive_keys=keys, prefix=path)
                )
    elif isinstance(value, (list, tuple, set)):
        for index, child in enumerate(value):
            found.extend(
                find_sensitive_paths(
                    child,
                    sensitive_keys=keys,
                    prefix=f"{prefix}[{index}]",
                )
            )
    elif isinstance(value, str) and redact_text(value) != value:
        found.append(prefix)
    return sorted(set(found))


def redact_value(
    value: Any,
    *,
    sensitive_keys: set[str] | None = None,
) -> Any:
    keys = sensitive_keys or sensitive_keys_from_environment()
    if isinstance(value, Mapping):
        return {
            str(raw_key): (
                REDACTED
                if is_sensitive_key(str(raw_key), keys)
                else redact_value(child, sensitive_keys=keys)
            )
            for raw_key, child in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_value(child, sensitive_keys=keys) for child in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
