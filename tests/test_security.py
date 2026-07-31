from __future__ import annotations

from control_plane.security import (
    REDACTED,
    find_sensitive_paths,
    fingerprint,
    redact_text,
    redact_value,
)


def test_fingerprint_is_canonical_and_input_sensitive() -> None:
    first = {"b": [2, {"z": True, "a": 1}], "a": "value"}
    reordered = {"a": "value", "b": [2, {"a": 1, "z": True}]}
    changed = {"a": "different", "b": [2, {"a": 1, "z": True}]}

    assert fingerprint(first) == fingerprint(reordered)
    assert fingerprint(first) != fingerprint(changed)


def test_redaction_handles_nested_mappings_and_lists() -> None:
    value = {
        "ticket_id": "T-100",
        "customer": {
            "email": "person@example.com",
            "profile": [{"phone_number": "+81-00-0000-0000"}],
        },
        "authorization": "Bearer secret",
    }

    redacted = redact_value(value)

    assert redacted["ticket_id"] == "T-100"
    assert redacted["customer"]["email"] == REDACTED
    assert redacted["customer"]["profile"][0]["phone_number"] == REDACTED
    assert redacted["authorization"] == REDACTED


def test_sensitive_paths_are_reported_without_values() -> None:
    paths = find_sensitive_paths(
        {"payload": {"password": "secret", "nested": [{"api_key": "key"}]}}
    )

    assert paths == ["$.payload.nested[0].api_key", "$.payload.password"]
    assert "secret" not in "".join(paths)


def test_error_text_redacts_bearer_and_assignments() -> None:
    text = "request failed Authorization: Bearer abc.def token=super-secret"
    redacted = redact_text(text)

    assert "abc.def" not in redacted
    assert "super-secret" not in redacted
    assert "[REDACTED]" in redacted
