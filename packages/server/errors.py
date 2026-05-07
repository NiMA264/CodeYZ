from __future__ import annotations

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def error_payload(code: str, message: str, hint: str = "", request_id: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "code": code,
        "message": message,
        "hint": hint,
    }
    if request_id:
        payload["request_id"] = request_id
    return payload


def error_response(status_code: int, code: str, message: str, hint: str = "", request_id: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code=code, message=message, hint=hint, request_id=request_id),
    )


def raise_api_error(
    status_code: int,
    code: str,
    message: str,
    hint: str = "",
    request_id: str | None = None,
) -> None:
    raise HTTPException(status_code=status_code, detail=error_payload(code, message, hint, request_id=request_id))
