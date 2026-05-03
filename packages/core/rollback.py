from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from packages.core.runtime_paths import ensure_runtime_dirs
from packages.tools.files import BLOCKED_DIRS, BLOCKED_NAMES, safe_path

SNAPSHOT_ROOT = ensure_runtime_dirs()["snapshots"]
ROLLBACK_FILE = SNAPSHOT_ROOT / "rollbacks.jsonl"
MAX_CONTENT_CHARS = 20000

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[^\s\n]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[^\s\n]+", re.IGNORECASE),
]

_ROLLBACKS: dict[str, dict] = {}
_ROLLBACK_ORDER: list[str] = []
_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def _sanitize_content(content: str) -> str:
    redacted = _redact(content)
    if len(redacted) > MAX_CONTENT_CHARS:
        return redacted[:MAX_CONTENT_CHARS] + "\n...[TRUNCATED]"
    return redacted


def _validate_file_path(file_path: str) -> Path:
    target = safe_path(file_path)
    if target.name in BLOCKED_NAMES:
        raise ValueError("Blocked secret file")
    if any(part in BLOCKED_DIRS for part in target.parts):
        raise ValueError("Blocked directory")
    return target


def _append_record(record: dict) -> None:
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    with ROLLBACK_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def create_snapshot(file_path: str) -> dict:
    target = _validate_file_path(file_path)
    rollback_id = uuid4().hex
    snapshot_dir = SNAPSHOT_ROOT / rollback_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    before_content = ""
    if target.exists():
        before_content = target.read_text(encoding="utf-8")
    safe_before = _sanitize_content(before_content)

    (snapshot_dir / "before.txt").write_text(safe_before, encoding="utf-8")
    return {
        "rollback_id": rollback_id,
        "file_path": file_path,
        "snapshot_dir": str(snapshot_dir),
        "before_content": safe_before,
    }


def create_rollback_record(file_path: str, before_content: str, after_content: str, diff: str) -> dict:
    target = _validate_file_path(file_path)
    rollback_id = uuid4().hex
    record = {
        "rollback_id": rollback_id,
        "file_path": file_path,
        "created_at": _now_iso(),
        "before_content": _sanitize_content(before_content),
        "after_content": _sanitize_content(after_content),
        "diff": _sanitize_content(diff),
        "absolute_path": str(target),
    }
    with _LOCK:
        _ROLLBACKS[rollback_id] = record
        _ROLLBACK_ORDER.append(rollback_id)
    _append_record(record)
    return record


def list_rollbacks() -> list[dict]:
    with _LOCK:
        ids = list(reversed(_ROLLBACK_ORDER))
        return [
            {
                "rollback_id": _ROLLBACKS[rid]["rollback_id"],
                "file_path": _ROLLBACKS[rid]["file_path"],
                "created_at": _ROLLBACKS[rid]["created_at"],
            }
            for rid in ids
        ]


def get_rollback(rollback_id: str) -> dict | None:
    with _LOCK:
        record = _ROLLBACKS.get(rollback_id)
        if record is None:
            return None
        return dict(record)


def rollback_change(rollback_id: str) -> dict:
    record = get_rollback(rollback_id)
    if record is None:
        raise ValueError("Rollback record not found")

    target = _validate_file_path(record["file_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(record["before_content"], encoding="utf-8")

    result = {
        "rollback_id": rollback_id,
        "file_path": record["file_path"],
        "restored_at": _now_iso(),
    }
    _append_record({"kind": "rollback_applied", **result})
    return result
