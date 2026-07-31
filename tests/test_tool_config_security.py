from __future__ import annotations

import pytest
from pydantic import ValidationError

from control_plane.tools import HttpOperation, HttpToolConfig


def test_sensitive_headers_must_reference_environment_variables() -> None:
    with pytest.raises(ValidationError, match="sensitive headers"):
        HttpToolConfig(
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer literal-secret"},
            operations={"reply": HttpOperation(path="/reply")},
        )


def test_sensitive_headers_accept_environment_reference() -> None:
    config = HttpToolConfig(
        base_url="https://api.example.com",
        headers={
            "Authorization": "Bearer ${SUPPORT_API_TOKEN}",
            "X-API-Key": "${SUPPORT_API_KEY}",
            "Accept": "application/json",
        },
        operations={"reply": HttpOperation(path="/reply")},
    )

    assert config.headers["Authorization"] == "Bearer ${SUPPORT_API_TOKEN}"
    assert config.headers["X-API-Key"] == "${SUPPORT_API_KEY}"
