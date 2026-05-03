from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from packages.server.auth import require_auth


def _make_request(host: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
        "client": (host, 12345),
    }
    return Request(scope)


def test_localhost_allowed_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEYZ_LOCAL_TOKEN", raising=False)
    require_auth(_make_request("127.0.0.1"))


def test_remote_blocked_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEYZ_LOCAL_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        require_auth(_make_request("8.8.8.8"))
    assert exc.value.status_code == 403


def test_x_api_key_required_when_token_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "abc123")
    with pytest.raises(HTTPException) as exc:
        require_auth(_make_request("127.0.0.1"))
    assert exc.value.status_code == 401

    require_auth(_make_request("127.0.0.1", headers=[(b"x-api-key", b"abc123")]))


def test_bearer_token_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEYZ_LOCAL_TOKEN", "abc123")
    require_auth(_make_request("127.0.0.1", headers=[(b"authorization", b"Bearer abc123")]))
