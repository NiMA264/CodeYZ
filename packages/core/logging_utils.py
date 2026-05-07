from __future__ import annotations

import json
import logging
import re
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[^\s\n]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[^\s\n]+", re.IGNORECASE),
]


def redact_secrets(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    if isinstance(value, dict):
        return {str(k): redact_secrets(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secrets(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "message": redact_secrets(record.getMessage()),
            "logger": record.name,
            "component": getattr(record, "component", ""),
            "request_id": getattr(record, "request_id", ""),
            "run_id": getattr(record, "run_id", ""),
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload["fields"] = redact_secrets(record.extra_fields)
        return json.dumps(payload, ensure_ascii=True)


def log_structured(
    logger: logging.Logger,
    level: int,
    message: str,
    *,
    component: str,
    request_id: str | None = None,
    run_id: str | None = None,
    **fields: Any,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "component": component,
            "request_id": request_id or "",
            "run_id": run_id or "",
            "extra_fields": fields,
        },
    )
