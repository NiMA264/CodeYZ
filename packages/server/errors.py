from __future__ import annotations

from fastapi import HTTPException


def error_payload(code: str, message: str, hint: str = "") -> dict[str, object]:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "hint": hint,
    }


def raise_api_error(status_code: int, code: str, message: str, hint: str = "") -> None:
    raise HTTPException(status_code=status_code, detail=error_payload(code, message, hint))

