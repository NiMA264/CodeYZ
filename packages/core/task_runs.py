from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from packages.core.persistence import atomic_write_text, file_lock
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
_LOCK = RLock()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts))
    except Exception:
        return None


def _duration_ms(created_at: str | None, finished_at: str | None) -> int:
    start = _parse_iso(created_at)
    end = _parse_iso(finished_at)
    if start is None or end is None:
        return 0
    delta = int((end - start).total_seconds() * 1000)
    return max(delta, 0)


def _risk_summary(levels: list[str]) -> str:
    if not levels:
        return "unknown"
    ordered = {"low": 1, "medium": 2, "high": 3}
    best = "unknown"
    score = 0
    for level in levels:
        lvl = str(level or "").lower()
        lvl_score = ordered.get(lvl, 0)
        if lvl_score > score:
            score = lvl_score
            best = lvl
    return best


def _derive_final_status(run_status: str, approvals_requested: int, approvals_applied: int) -> str:
    normalized = str(run_status or "").lower()
    if normalized in {"done", "success"}:
        return "success"
    if normalized in {"failed", "blocked", "budget_blocked"}:
        return "failed"
    if normalized in {"cancelled", "canceled"}:
        return "cancelled"
    if approvals_requested > approvals_applied:
        return "approval_required"
    return "failed"


def _extract_event_data(event: dict) -> dict:
    data = event.get("data")
    if isinstance(data, dict):
        return data
    return {}


def _build_run_metrics(run: dict) -> dict:
    events = run.get("events", []) if isinstance(run.get("events"), list) else []
    created_at = str(run.get("created_at") or "")
    finished_at = str(run.get("finished_at") or "")
    run_status = str(run.get("status") or "")
    model = str(run.get("model") or "")
    profile = str(run.get("profile") or "custom")

    files_changed: set[str] = set()
    rollback_ids: set[str] = set()
    added_lines = 0
    removed_lines = 0
    hunks_count = 0
    approvals_requested = 0
    approvals_applied = 0
    patches_generated = 0
    patches_applied = 0
    risk_levels: list[str] = []
    token_input = 0
    token_output = 0
    tests_run = 0
    tests_passed = 0
    tests_failed = 0
    tool_usage = {"search": False, "plugins": False, "tests": False, "files": False}

    for event in events:
        event_type = str(event.get("event_type") or "")
        data = _extract_event_data(event)

        if event_type == "tool_decision":
            tool_usage["search"] = bool(data.get("use_search")) or tool_usage["search"]
            tool_usage["plugins"] = bool(data.get("use_plugins")) or tool_usage["plugins"]
            tool_usage["tests"] = bool(data.get("use_tests")) or tool_usage["tests"]
            tool_usage["files"] = bool(data.get("use_files")) or tool_usage["files"]

        if event_type == "patch":
            generated = data.get("patches")
            if isinstance(generated, list):
                patches_generated += len(generated)
            else:
                patches_generated += 1

        if event_type == "diff":
            file_path = str(data.get("file") or "")
            if file_path:
                files_changed.add(file_path)
                patches_applied += 1
            added_lines += int(data.get("added_lines") or 0)
            removed_lines += int(data.get("removed_lines") or 0)
            hunks_count += int(data.get("hunks_count") or 0)
            risk_lvl = str(data.get("risk_level") or "")
            if risk_lvl:
                risk_levels.append(risk_lvl)
            rollback_id = str(data.get("rollback_id") or "")
            if rollback_id:
                rollback_ids.add(rollback_id)

        if event_type == "approval_required":
            approvals_requested += 1
            file_path = str(data.get("file") or "")
            if file_path:
                files_changed.add(file_path)
            stats = data.get("stats") if isinstance(data.get("stats"), dict) else {}
            added_lines += int(data.get("added_lines") or stats.get("additions", 0) or 0)
            removed_lines += int(data.get("removed_lines") or stats.get("deletions", 0) or 0)
            hunks_count += int(data.get("hunks_count") or 0)
            risk_lvl = str(data.get("risk_level") or "")
            if risk_lvl:
                risk_levels.append(risk_lvl)

        if event_type == "approval_applied":
            approvals_applied += 1
            file_path = str(data.get("file") or "")
            if file_path:
                files_changed.add(file_path)
            patches_applied += 1
            added_lines += int(data.get("added_lines") or 0)
            removed_lines += int(data.get("removed_lines") or 0)
            hunks_count += int(data.get("hunks_count") or 0)
            rollback_id = str(data.get("rollback_id") or "")
            if rollback_id:
                rollback_ids.add(rollback_id)
            risk_lvl = str(data.get("risk_level") or "")
            if risk_lvl:
                risk_levels.append(risk_lvl)

        if event_type == "test":
            if isinstance(data.get("ok"), bool):
                tests_run += 1
                if bool(data.get("ok")):
                    tests_passed += 1
                else:
                    tests_failed += 1

        token_input += int(data.get("estimated_input_tokens") or 0)
        token_output += int(data.get("estimated_output_tokens") or 0)

    final_status = _derive_final_status(run_status, approvals_requested, approvals_applied)
    return {
        "run_id": str(run.get("run_id") or ""),
        "start_time": created_at,
        "end_time": finished_at,
        "duration_ms": _duration_ms(created_at, finished_at),
        "final_status": final_status,
        "files_changed_count": len(files_changed),
        "added_lines": added_lines,
        "removed_lines": removed_lines,
        "hunks_count": hunks_count,
        "approvals_requested": approvals_requested,
        "approvals_applied": approvals_applied,
        "patches_generated": patches_generated,
        "patches_applied": patches_applied,
        "rollback_count": len(rollback_ids),
        "tool_usage": tool_usage,
        "token_usage": {
            "input_tokens": token_input,
            "output_tokens": token_output,
            "total_tokens": token_input + token_output,
        },
        "model": model,
        "profile": profile or "custom",
        "risk_level_summary": _risk_summary(risk_levels),
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


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
    with _LOCK:
        with file_lock(RUNS_FILE):
            RUNS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with RUNS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _save_approval_state(run_id: str, source_event_id: str, status: str) -> None:
    _append_jsonl(
        {
            "kind": "approval_state",
            "run_id": run_id,
            "source_event_id": source_event_id,
            "status": status,
            "ts": _now_iso(),
        }
    )


def create_run(task: str, model: str | None, access_level: str | None, profile: str | None = None) -> str:
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
        "profile": _sanitize(profile or "custom"),
        "events": [],
        "approval_states": {},
        "metrics": {},
    }
    with _LOCK:
        _RUNS[run_id] = run
        _RUN_ORDER.append(run_id)
    _append_jsonl(
        {
            "kind": "run_created",
            "run_id": run_id,
            "task": run["task"],
            "model": run["model"],
            "access_level": run["access_level"],
            "status": run["status"],
            "summary": run["summary"],
            "created_at": run["created_at"],
            "finished_at": run["finished_at"],
            "profile": run["profile"],
            "approval_states": run["approval_states"],
            "metrics": run["metrics"],
            "ts": run["created_at"],
        }
    )
    return run_id


def add_event(
    run_id: str,
    event_type: str,
    title: str,
    data=None,
    agent_role: str | None = None,
) -> dict:
    event = {
        "event_id": uuid4().hex,
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
        run["metrics"] = _build_run_metrics(run)
    _append_jsonl(
        {
            "kind": "run_finished",
            "run_id": run_id,
            "status": status,
            "summary": _sanitize(summary or ""),
            "metrics": _RUNS.get(run_id, {}).get("metrics", {}),
            "ts": _now_iso(),
        }
    )
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
                "metrics": _RUNS[rid].get("metrics", {}),
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
            "profile": run.get("profile", "custom"),
            "metrics": run.get("metrics", {}),
            "events": list(run["events"]),
        }


def get_event(run_id: str, event_id: str) -> dict | None:
    run = get_run(run_id)
    if run is None:
        return None
    for event in run.get("events", []):
        if str(event.get("event_id", "")) == event_id:
            return event
    return None


def has_approval_applied(run_id: str, source_event_id: str) -> bool:
    run = get_run(run_id)
    if run is None:
        return False
    for event in run.get("events", []):
        if event.get("event_type") != "approval_applied":
            continue
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        if str(data.get("source_event_id", "")) == source_event_id:
            return True
    return False


def claim_approval_event(run_id: str, source_event_id: str) -> bool:
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return False
        states = run.setdefault("approval_states", {})
        current = str(states.get(source_event_id, ""))
        if current in {"claimed", "applied"}:
            return False
        for event in run.get("events", []):
            if event.get("event_type") != "approval_applied":
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            if str(data.get("source_event_id", "")) == source_event_id:
                states[source_event_id] = "applied"
                _save_approval_state(run_id, source_event_id, "applied")
                return False
        states[source_event_id] = "claimed"
        _save_approval_state(run_id, source_event_id, "claimed")
        return True


def mark_approval_event(run_id: str, source_event_id: str, status: str) -> None:
    if status not in {"claimed", "applied", "failed"}:
        raise ValueError("Invalid approval status")
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return
        states = run.setdefault("approval_states", {})
        states[source_event_id] = status
        _save_approval_state(run_id, source_event_id, status)


def _load_runs_unlocked() -> None:
    if not RUNS_FILE.exists():
        _RUNS.clear()
        _RUN_ORDER.clear()
        return
    runs: dict[str, dict] = {}
    order: list[str] = []
    try:
        lines = RUNS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        kind = str(record.get("kind", ""))
        run_id = str(record.get("run_id", ""))
        if not run_id:
            continue

        if kind == "run_created":
            run = {
                "run_id": run_id,
                "task": _sanitize(str(record.get("task", ""))),
                "model": str(record.get("model", "")),
                "access_level": str(record.get("access_level", "")),
                "status": _sanitize(str(record.get("status", "running"))),
                "summary": _sanitize(str(record.get("summary", ""))),
                "created_at": str(record.get("created_at", record.get("ts", _now_iso()))),
                "finished_at": record.get("finished_at"),
                "profile": _sanitize(str(record.get("profile", "custom") or "custom")),
                "events": [],
                "approval_states": {},
                "metrics": record.get("metrics", {}) if isinstance(record.get("metrics"), dict) else {},
            }
            approval_states = record.get("approval_states", {})
            if isinstance(approval_states, dict):
                run["approval_states"] = {
                    str(k): str(v)
                    for k, v in approval_states.items()
                    if str(v) in {"claimed", "applied", "failed"}
                }
            runs[run_id] = run
            if run_id not in order:
                order.append(run_id)
            continue

        run = runs.get(run_id)
        if run is None:
            continue

        if kind == "event":
            event = {
                "event_id": str(record.get("event_id", uuid4().hex)),
                "ts": str(record.get("ts", _now_iso())),
                "event_type": str(record.get("event_type", "unknown")),
                "agent_role": _sanitize(str(record.get("agent_role", ""))),
                "title": _sanitize(str(record.get("title", ""))),
                "data": _sanitize(record.get("data")),
            }
            run["events"].append(event)
        elif kind == "run_finished":
            run["status"] = _sanitize(str(record.get("status", run["status"])))
            run["summary"] = _sanitize(str(record.get("summary", run["summary"])))
            run["finished_at"] = str(record.get("ts", run["finished_at"] or _now_iso()))
            metrics = record.get("metrics")
            if isinstance(metrics, dict):
                run["metrics"] = metrics
            elif not run.get("metrics"):
                run["metrics"] = _build_run_metrics(run)
        elif kind == "approval_state":
            source_event_id = str(record.get("source_event_id", ""))
            status = str(record.get("status", ""))
            if source_event_id and status in {"claimed", "applied", "failed"}:
                run.setdefault("approval_states", {})[source_event_id] = status

    _RUNS.clear()
    _RUNS.update(runs)
    _RUN_ORDER.clear()
    _RUN_ORDER.extend(order)


def load_runs() -> None:
    with _LOCK:
        _load_runs_unlocked()


def initialize_task_runs_storage() -> None:
    load_runs()


def compact_runs_storage() -> None:
    with _LOCK:
        with file_lock(RUNS_FILE):
            _load_runs_unlocked()
            run_ids = list(_RUN_ORDER)
            runs = [dict(_RUNS[rid]) for rid in run_ids if rid in _RUNS]
            records: list[dict] = []
            for run in runs:
                run_id = str(run.get("run_id", ""))
                if not run_id:
                    continue
                approval_states = run.get("approval_states", {})
                if not isinstance(approval_states, dict):
                    approval_states = {}
                cleaned_states = {
                    str(k): str(v)
                    for k, v in approval_states.items()
                    if str(v) in {"claimed", "applied", "failed"}
                }

                records.append(
                    {
                        "kind": "run_created",
                        "run_id": run_id,
                        "task": run.get("task", ""),
                        "model": run.get("model", ""),
                        "access_level": run.get("access_level", ""),
                        "status": run.get("status", "running"),
                        "summary": run.get("summary", ""),
                        "created_at": run.get("created_at", _now_iso()),
                        "finished_at": run.get("finished_at"),
                        "profile": run.get("profile", "custom"),
                        "approval_states": cleaned_states,
                        "metrics": run.get("metrics", {}) if isinstance(run.get("metrics"), dict) else {},
                        "ts": run.get("created_at", _now_iso()),
                    }
                )

                for event in run.get("events", []):
                    if not isinstance(event, dict):
                        continue
                    records.append(
                        {
                            "kind": "event",
                            "run_id": run_id,
                            "event_id": str(event.get("event_id", uuid4().hex)),
                            "event_type": str(event.get("event_type", "unknown")),
                            "agent_role": str(event.get("agent_role", "")),
                            "title": str(event.get("title", "")),
                            "data": event.get("data"),
                            "ts": str(event.get("ts", _now_iso())),
                        }
                    )

                finished_at = run.get("finished_at")
                status = str(run.get("status", "running"))
                summary = str(run.get("summary", ""))
                if finished_at or status != "running" or summary:
                    metrics = run.get("metrics", {})
                    if not isinstance(metrics, dict) or not metrics:
                        metrics = _build_run_metrics(run)
                    records.append(
                        {
                            "kind": "run_finished",
                            "run_id": run_id,
                            "status": status,
                            "summary": summary,
                            "metrics": metrics,
                            "ts": str(finished_at or _now_iso()),
                        }
                    )

            content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
            if content:
                content += "\n"
            atomic_write_text(RUNS_FILE, content)
