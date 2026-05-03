from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from packages.core.runtime_paths import ensure_runtime_dirs

RUNS_FILE = ensure_runtime_dirs()["runs"] / "runs.jsonl"
MAX_EVENT_CHARS = 4000

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[^\s\n]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[^\s\n]+", re.IGNORECASE),
]

_RUNS: dict[str, dict] = {}
_RUN_ORDER: list[str] = []
_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_text(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def _sanitize(value):
    if isinstance(value, str):
        redacted = _redact_text(value)
        if len(redacted) > MAX_EVENT_CHARS:
            return redacted[:MAX_EVENT_CHARS] + "\n...[TRUNCATED]"
        return redacted
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def _append_jsonl(record: dict) -> None:
    RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def create_run(task: str, model: str | None, access_level: str | None) -> str:
    run_id = uuid4().hex
    run = {
        "run_id": run_id,
        "task": _sanitize(task),
        "model": model or "",
        "access_level": access_level or "",
        "status": "running",
        "summary": "",
        "created_at": _now_iso(),
        "finished_at": None,
        "events": [],
    }
    with _LOCK:
        _RUNS[run_id] = run
        _RUN_ORDER.append(run_id)
    _append_jsonl({"kind": "run_created", "run_id": run_id, "task": run["task"], "ts": run["created_at"]})
    return run_id


def add_event(
    run_id: str,
    event_type: str,
    title: str,
    data=None,
    agent_role: str | None = None,
) -> dict:
    event = {
        "ts": _now_iso(),
        "event_type": event_type,
        "agent_role": _sanitize(agent_role or ""),
        "title": _sanitize(title),
        "data": _sanitize(data),
    }
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise ValueError("Unknown run_id")
        run["events"].append(event)
    _append_jsonl({"kind": "event", "run_id": run_id, **event})
    return event


def finish_run(run_id: str, status: str, summary: str | None = None) -> dict:
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise ValueError("Unknown run_id")
        run["status"] = _sanitize(status)
        run["summary"] = _sanitize(summary or "")
        run["finished_at"] = _now_iso()
    _append_jsonl({"kind": "run_finished", "run_id": run_id, "status": status, "summary": _sanitize(summary or ""), "ts": _now_iso()})
    return get_run(run_id)


def list_runs() -> list[dict]:
    with _LOCK:
        ids = list(reversed(_RUN_ORDER))
        return [
            {
                "run_id": _RUNS[rid]["run_id"],
                "task": _RUNS[rid]["task"],
                "status": _RUNS[rid]["status"],
                "model": _RUNS[rid]["model"],
                "access_level": _RUNS[rid]["access_level"],
                "created_at": _RUNS[rid]["created_at"],
                "finished_at": _RUNS[rid]["finished_at"],
                "events_count": len(_RUNS[rid]["events"]),
            }
            for rid in ids
        ]


def get_run(run_id: str) -> dict | None:
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return None
        return {
            "run_id": run["run_id"],
            "task": run["task"],
            "model": run["model"],
            "access_level": run["access_level"],
            "status": run["status"],
            "summary": run["summary"],
            "created_at": run["created_at"],
            "finished_at": run["finished_at"],
            "events": list(run["events"]),
        }
