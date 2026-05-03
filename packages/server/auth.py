import os

from fastapi import HTTPException, Request, status

_LOCALHOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_local_request(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    host = (client.host or "").lower()
    return host in _LOCALHOSTS


def require_auth(request: Request) -> None:
    configured_token = os.getenv("CODEYZ_LOCAL_TOKEN")

    if configured_token:
        header_token = request.headers.get("x-api-key")
        if not header_token:
            auth_header = request.headers.get("authorization", "")
            if auth_header.lower().startswith("bearer "):
                header_token = auth_header[7:].strip()

        if header_token != configured_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        return

    if not _is_local_request(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local access only",
        )
