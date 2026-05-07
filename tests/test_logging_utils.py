from __future__ import annotations

import json
import logging

from packages.core.logging_utils import JsonFormatter, redact_secrets


def test_redact_secrets_in_text() -> None:
    raw = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890"
    out = redact_secrets(raw)
    assert "sk-" not in out
    assert "[REDACTED]" in out


def test_json_formatter_redacts_fields() -> None:
    logger = logging.getLogger("test.logging")
    record = logger.makeRecord(
        "test.logging",
        logging.INFO,
        fn="x.py",
        lno=1,
        msg="token sk-abcdefghijklmnopqrstuvwxyz1234567890",
        args=(),
        exc_info=None,
        extra={"component": "api", "request_id": "r1", "run_id": "run1", "extra_fields": {"key": "OPENAI_API_KEY=abc"}},
    )
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    assert payload["component"] == "api"
    assert payload["request_id"] == "r1"
    assert payload["run_id"] == "run1"
    assert "sk-" not in payload["message"]
    assert "OPENAI_API_KEY" not in json.dumps(payload)
