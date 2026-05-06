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
RUN_PHASES = {
    "created",
    "planning",
    "analyzing",
    "tool_selection",
    "patching",
    "testing",
    "approval_required",
    "applying",
    "completed",
    "failed",
    "cancelled",
}
RESUME_STATES = {
    "resumable",
    "waiting_for_approval",
    "completed",
    "failed_non_resumable",
    "cancelled",
}


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


def _derive_phase_from_events(run: dict) -> str:
    events = run.get("events", []) if isinstance(run.get("events"), list) else []
    status = str(run.get("status") or "").lower()
    if status in {"done", "success"}:
        return "completed"
    if status in {"failed", "blocked", "budget_blocked"}:
        return "failed"
    if status in {"cancelled", "canceled"}:
        return "cancelled"

    approval_required_ids: set[str] = set()
    approval_applied_ids: set[str] = set()
    for event in events:
        event_type = str(event.get("event_type") or "")
        if event_type == "approval_required":
            approval_required_ids.add(str(event.get("event_id") or ""))
        elif event_type == "approval_applied":
            data = _extract_event_data(event)
            source_event_id = str(data.get("source_event_id") or "")
            if source_event_id:
                approval_applied_ids.add(source_event_id)
    if any(event_id and event_id not in approval_applied_ids for event_id in approval_required_ids):
        return "approval_required"

    event_to_phase = {
        "tool_decision": "tool_selection",
        "analyze": "analyzing",
        "plan": "planning",
        "patch": "patching",
        "diff": "patching",
        "approval_applied": "applying",
        "test": "testing",
        "build": "testing",
        "result": "completed",
        "error": "failed",
    }
    for event in reversed(events):
        mapped = event_to_phase.get(str(event.get("event_type") or ""))
        if mapped:
            return mapped
    return "created"


def _resolve_phase(run: dict) -> str:
    phase = str(run.get("phase") or "")
    if phase in RUN_PHASES and not (phase == "created" and isinstance(run.get("events"), list) and run.get("events")):
        return phase
    return _derive_phase_from_events(run)


def _build_run_metrics(run: dict, live: bool = False) -> dict:
    events = run.get("events", []) if isinstance(run.get("events"), list) else []
    created_at = str(run.get("created_at") or "")
    finished_at = str(run.get("finished_at") or "")
    phase = _resolve_phase(run)
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
    policy_violations_count = 0
    policy_warnings_count = 0
    blocked_actions_count = 0
    policy_trigger_reasons: list[str] = []
    constraint_evaluations = 0
    approval_triggers = 0
    blocked_constraints: list[str] = []
    warning_constraints: list[str] = []
    runtime_limit_hits = 0
    checkpoints_created = len(run.get("checkpoints", [])) if isinstance(run.get("checkpoints"), list) else 0
    approval_waitpoints = 0
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
            approval_waitpoints += 1
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
        if event_type == "policy_warning":
            policy_warnings_count += 1
            reason = str(data.get("reason") or "")
            if reason:
                policy_trigger_reasons.append(reason)
                warning_constraints.append(reason)
            if isinstance(data.get("constraint_result"), dict):
                constraint_evaluations += 1
        if event_type == "policy_block":
            policy_violations_count += 1
            blocked_actions_count += 1
            reason = str(data.get("reason") or "")
            if reason:
                policy_trigger_reasons.append(reason)
                blocked_constraints.append(reason)
                if reason == "max_runtime_minutes":
                    runtime_limit_hits += 1
            if isinstance(data.get("constraint_result"), dict):
                constraint_evaluations += 1
        if event_type == "policy_approval_required":
            policy_violations_count += 1
            reason = str(data.get("reason") or "")
            if reason:
                policy_trigger_reasons.append(reason)
                approval_triggers += 1
            if isinstance(data.get("constraint_result"), dict):
                constraint_evaluations += 1

        token_input += int(data.get("estimated_input_tokens") or 0)
        token_output += int(data.get("estimated_output_tokens") or 0)

    final_status = _derive_final_status(run_status, approvals_requested, approvals_applied)
    if live and not finished_at and run_status == "running":
        if phase == "approval_required":
            final_status = "approval_required"
        else:
            final_status = "running"
    end_time = finished_at or (_now_iso() if live else "")
    return {
        "run_id": str(run.get("run_id") or ""),
        "start_time": created_at,
        "end_time": end_time,
        "duration_ms": _duration_ms(created_at, end_time),
        "final_status": final_status,
        "current_phase": phase,
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
        "policy_violations_count": policy_violations_count,
        "policy_warnings_count": policy_warnings_count,
        "blocked_actions_count": blocked_actions_count,
        "policy_trigger_reasons": sorted(set(policy_trigger_reasons))[:20],
        "constraint_evaluations": constraint_evaluations,
        "approval_triggers": approval_triggers,
        "blocked_constraints": sorted(set(blocked_constraints))[:20],
        "warning_constraints": sorted(set(warning_constraints))[:20],
        "runtime_limit_hits": runtime_limit_hits,
        "checkpoints_created": checkpoints_created,
        "approval_waitpoints": approval_waitpoints,
        "resume_candidates": 1 if bool(_derive_resume_state(run).get("resume_candidate")) else 0,
        "resumable_runs": 1 if str(_derive_resume_state(run).get("state")) in {"resumable", "waiting_for_approval"} else 0,
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


def _normalize_event_for_replay(run: dict, raw_event: dict, sequence: int) -> dict:
    phase = _resolve_phase(run)
    status = str(run.get("status", "running"))
    event = {
        "event_id": str(raw_event.get("event_id", uuid4().hex)),
        "ts": str(raw_event.get("ts", _now_iso())),
        "event_type": str(raw_event.get("event_type", "unknown")),
        "agent_role": _sanitize(str(raw_event.get("agent_role", ""))),
        "title": _sanitize(str(raw_event.get("title", ""))),
        "data": _sanitize(raw_event.get("data")),
        "sequence": int(sequence),
        "phase": phase,
        "status": status,
        "metrics_snapshot": {
            "files_changed_count": int(raw_event.get("metrics_snapshot", {}).get("files_changed_count", 0))
            if isinstance(raw_event.get("metrics_snapshot"), dict)
            else int((_build_run_metrics(run, live=True)).get("files_changed_count", 0)),
            "added_lines": int((_build_run_metrics(run, live=True)).get("added_lines", 0)),
            "removed_lines": int((_build_run_metrics(run, live=True)).get("removed_lines", 0)),
            "approvals_requested": int((_build_run_metrics(run, live=True)).get("approvals_requested", 0)),
            "approvals_applied": int((_build_run_metrics(run, live=True)).get("approvals_applied", 0)),
            "policy_violations_count": int((_build_run_metrics(run, live=True)).get("policy_violations_count", 0)),
            "policy_warnings_count": int((_build_run_metrics(run, live=True)).get("policy_warnings_count", 0)),
        },
    }
    return event


def _pending_approval_event_ids(run: dict) -> list[str]:
    events = run.get("events", []) if isinstance(run.get("events"), list) else []
    required: list[str] = []
    applied: set[str] = set()
    for ev in events:
        if str(ev.get("event_type", "")) == "approval_required":
            required.append(str(ev.get("event_id", "")))
        elif str(ev.get("event_type", "")) == "approval_applied":
            data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
            src = str(data.get("source_event_id", ""))
            if src:
                applied.add(src)
    out = []
    for event_id in required:
        if event_id and event_id not in applied:
            out.append(event_id)
    return out


def _derive_resume_state(run: dict) -> dict:
    status = str(run.get("status", "running")).lower()
    phase = _resolve_phase(run)
    checkpoints = run.get("checkpoints", []) if isinstance(run.get("checkpoints"), list) else []
    last_checkpoint = checkpoints[-1] if checkpoints else None
    pending_approvals = _pending_approval_event_ids(run)
    if status in {"done", "success"}:
        state = "completed"
        reason = "run_completed"
    elif status in {"cancelled", "canceled"}:
        state = "cancelled"
        reason = "run_cancelled"
    elif pending_approvals or phase == "approval_required":
        state = "waiting_for_approval"
        reason = "pending_approval"
    elif status in {"failed", "blocked", "budget_blocked"}:
        state = "failed_non_resumable"
        reason = "failed_terminal"
    else:
        state = "resumable"
        reason = "active_checkpoint"
    if state not in RESUME_STATES:
        state = "failed_non_resumable"
        reason = "unknown_state"
    return {
        "state": state,
        "resume_candidate": state in {"resumable", "waiting_for_approval"},
        "latest_checkpoint_id": str(last_checkpoint.get("checkpoint_id", "")) if isinstance(last_checkpoint, dict) else "",
        "resume_sequence": int(last_checkpoint.get("sequence", 0) or 0) if isinstance(last_checkpoint, dict) else 0,
        "resumable_phase": str(last_checkpoint.get("phase", phase)) if isinstance(last_checkpoint, dict) else phase,
        "reason": reason,
        "pending_approvals": pending_approvals,
    }


def _build_replay_payload(run: dict) -> dict:
    events = run.get("events", []) if isinstance(run.get("events"), list) else []
    normalized = sorted(
        [event for event in events if isinstance(event, dict)],
        key=lambda ev: (int(ev.get("sequence", 0) or 0), str(ev.get("ts", "")), str(ev.get("event_id", ""))),
    )
    phase_sections: list[dict] = []
    current: dict | None = None
    for event in normalized:
        phase = str(event.get("phase", "unknown"))
        seq = int(event.get("sequence", 0) or 0)
        if current is None or str(current.get("phase")) != phase:
            current = {"phase": phase, "start_sequence": seq, "end_sequence": seq, "count": 1}
            phase_sections.append(current)
        else:
            current["end_sequence"] = seq
            current["count"] = int(current.get("count", 0)) + 1
    first_seq = int(normalized[0].get("sequence", 0) or 0) if normalized else 0
    last_seq = int(normalized[-1].get("sequence", 0) or 0) if normalized else 0
    return {
        "total_events": len(normalized),
        "first_sequence": first_seq,
        "last_sequence": last_seq,
        "phase_sections": phase_sections,
        "checkpoints": [
            {
                "checkpoint_id": str(cp.get("checkpoint_id", "")),
                "sequence": int(cp.get("sequence", 0) or 0),
                "phase": str(cp.get("phase", "unknown")),
                "status": str(cp.get("status", "unknown")),
                "created_at": str(cp.get("created_at", "")),
                "reason": str(cp.get("reason", "")),
            }
            for cp in (run.get("checkpoints", []) if isinstance(run.get("checkpoints"), list) else [])
            if isinstance(cp, dict)
        ],
    }


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


def create_run(
    task: str,
    model: str | None,
    access_level: str | None,
    profile: str | None = None,
    policy: dict | None = None,
) -> str:
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
        "policy": _sanitize(policy or {}),
        "phase": "created",
        "events": [],
        "checkpoints": [],
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
            "policy": run["policy"],
            "phase": run["phase"],
            "checkpoints": run["checkpoints"],
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
        sequence = len(run.get("events", [])) + 1
        normalized = _normalize_event_for_replay(run, event, sequence)
        run["events"].append(normalized)
    _append_jsonl({"kind": "event", "run_id": run_id, **normalized})
    return normalized


def create_checkpoint(run_id: str, reason: str, current_action: str | None = None) -> dict | None:
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return None
        checkpoint = {
            "checkpoint_id": uuid4().hex,
            "run_id": run_id,
            "sequence": len(run.get("events", [])),
            "phase": _resolve_phase(run),
            "status": str(run.get("status", "running")),
            "metrics_snapshot": _build_run_metrics(run, live=True),
            "active_policy": run.get("policy", {}) if isinstance(run.get("policy"), dict) else {},
            "current_profile": str(run.get("profile", "custom")),
            "pending_approvals": _pending_approval_event_ids(run),
            "resume_candidate": False,
            "reason": str(reason or "manual"),
            "current_action": str(current_action or ""),
            "created_at": _now_iso(),
        }
        run.setdefault("checkpoints", []).append(checkpoint)
        resume = _derive_resume_state(run)
        checkpoint["resume_candidate"] = bool(resume.get("resume_candidate"))
    _append_jsonl({"kind": "checkpoint", "run_id": run_id, **checkpoint})
    return checkpoint


def finish_run(run_id: str, status: str, summary: str | None = None) -> dict:
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            raise ValueError("Unknown run_id")
        run["status"] = _sanitize(status)
        run["summary"] = _sanitize(summary or "")
        run["finished_at"] = _now_iso()
        if run["status"] in {"done", "success"}:
            run["phase"] = "completed"
        elif run["status"] in {"failed", "blocked", "budget_blocked"}:
            run["phase"] = "failed"
        elif run["status"] in {"cancelled", "canceled"}:
            run["phase"] = "cancelled"
        run["metrics"] = _build_run_metrics(run)
    create_checkpoint(run_id, reason=f"before_finish:{status}", current_action="finish_run")
    _append_jsonl(
        {
            "kind": "run_finished",
            "run_id": run_id,
            "status": status,
            "summary": _sanitize(summary or ""),
            "phase": _RUNS.get(run_id, {}).get("phase", ""),
            "metrics": _RUNS.get(run_id, {}).get("metrics", {}),
            "ts": _now_iso(),
        }
    )
    return get_run(run_id)


def list_runs() -> list[dict]:
    with _LOCK:
        ids = list(reversed(_RUN_ORDER))
        def _metrics_for(run: dict) -> dict:
            if str(run.get("status", "")) == "running":
                return _build_run_metrics(run, live=True)
            metrics = run.get("metrics", {})
            if isinstance(metrics, dict) and metrics:
                return metrics
            return _build_run_metrics(run)

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
                "policy": _RUNS[rid].get("policy", {}),
                "phase": _resolve_phase(_RUNS[rid]),
                "metrics": _metrics_for(_RUNS[rid]),
                "resume_state": _derive_resume_state(_RUNS[rid]),
                "checkpoints_count": len(_RUNS[rid].get("checkpoints", [])) if isinstance(_RUNS[rid].get("checkpoints"), list) else 0,
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
            "policy": run.get("policy", {}),
            "phase": _resolve_phase(run),
            "metrics": _build_run_metrics(run, live=(str(run.get("status", "")) == "running")),
            "events": list(run["events"]),
            "replay": _build_replay_payload(run),
            "checkpoints": list(run.get("checkpoints", [])) if isinstance(run.get("checkpoints"), list) else [],
            "resume_state": _derive_resume_state(run),
        }


def set_run_phase(run_id: str, phase: str) -> dict | None:
    safe_phase = str(phase or "").strip().lower()
    if safe_phase not in RUN_PHASES:
        safe_phase = "created"
    with _LOCK:
        run = _RUNS.get(run_id)
        if run is None:
            return None
        previous = str(run.get("phase", "created"))
        run["phase"] = safe_phase
    _append_jsonl({"kind": "run_phase", "run_id": run_id, "phase": safe_phase, "ts": _now_iso()})
    if previous != safe_phase:
        create_checkpoint(run_id, reason=f"phase:{previous}->{safe_phase}", current_action=safe_phase)
    return get_run(run_id)


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
                "policy": _sanitize(record.get("policy", {}) if isinstance(record.get("policy"), dict) else {}),
                "phase": str(record.get("phase", "created") or "created"),
                "events": [],
                "checkpoints": [],
                "approval_states": {},
                "metrics": record.get("metrics", {}) if isinstance(record.get("metrics"), dict) else {},
            }
            checkpoints = record.get("checkpoints", [])
            if isinstance(checkpoints, list):
                run["checkpoints"] = [_sanitize(cp) for cp in checkpoints if isinstance(cp, dict)]
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
            raw_event = {
                "event_id": str(record.get("event_id", uuid4().hex)),
                "ts": str(record.get("ts", _now_iso())),
                "event_type": str(record.get("event_type", "unknown")),
                "agent_role": _sanitize(str(record.get("agent_role", ""))),
                "title": _sanitize(str(record.get("title", ""))),
                "data": _sanitize(record.get("data")),
                "sequence": int(record.get("sequence", 0) or 0),
            }
            seq = int(raw_event.get("sequence", 0) or 0)
            if seq <= 0:
                seq = len(run.get("events", [])) + 1
            event = _normalize_event_for_replay(run, raw_event, seq)
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
            phase = str(record.get("phase", "") or "")
            if phase in RUN_PHASES:
                run["phase"] = phase
            else:
                run["phase"] = _derive_phase_from_events(run)
        elif kind == "run_phase":
            phase = str(record.get("phase", "") or "")
            if phase in RUN_PHASES:
                run["phase"] = phase
        elif kind == "checkpoint":
            checkpoint = {
                "checkpoint_id": str(record.get("checkpoint_id", uuid4().hex)),
                "run_id": run_id,
                "sequence": int(record.get("sequence", 0) or 0),
                "phase": str(record.get("phase", run.get("phase", "created"))),
                "status": str(record.get("status", run.get("status", "running"))),
                "metrics_snapshot": _sanitize(record.get("metrics_snapshot", {}) if isinstance(record.get("metrics_snapshot"), dict) else {}),
                "active_policy": _sanitize(record.get("active_policy", {}) if isinstance(record.get("active_policy"), dict) else {}),
                "current_profile": str(record.get("current_profile", run.get("profile", "custom"))),
                "pending_approvals": [str(x) for x in (record.get("pending_approvals", []) if isinstance(record.get("pending_approvals"), list) else [])],
                "resume_candidate": bool(record.get("resume_candidate", False)),
                "reason": str(record.get("reason", "")),
                "current_action": str(record.get("current_action", "")),
                "created_at": str(record.get("created_at", record.get("ts", _now_iso()))),
            }
            run.setdefault("checkpoints", []).append(checkpoint)
        elif kind == "approval_state":
            source_event_id = str(record.get("source_event_id", ""))
            status = str(record.get("status", ""))
            if source_event_id and status in {"claimed", "applied", "failed"}:
                run.setdefault("approval_states", {})[source_event_id] = status

    _RUNS.clear()
    _RUNS.update(runs)
    for run in _RUNS.values():
        events = run.get("events", [])
        if isinstance(events, list):
            events.sort(key=lambda ev: (int(ev.get("sequence", 0) or 0), str(ev.get("ts", "")), str(ev.get("event_id", ""))))
        checkpoints = run.get("checkpoints", [])
        if isinstance(checkpoints, list):
            checkpoints.sort(key=lambda cp: (int(cp.get("sequence", 0) or 0), str(cp.get("created_at", "")), str(cp.get("checkpoint_id", ""))))
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
                        "policy": run.get("policy", {}) if isinstance(run.get("policy"), dict) else {},
                        "phase": _resolve_phase(run),
                        "checkpoints": run.get("checkpoints", []) if isinstance(run.get("checkpoints"), list) else [],
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
                            "sequence": int(event.get("sequence", 0) or 0),
                            "phase": str(event.get("phase", "")),
                            "status": str(event.get("status", "")),
                            "metrics_snapshot": event.get("metrics_snapshot", {}) if isinstance(event.get("metrics_snapshot"), dict) else {},
                            "ts": str(event.get("ts", _now_iso())),
                        }
                    )

                for checkpoint in run.get("checkpoints", []):
                    if not isinstance(checkpoint, dict):
                        continue
                    records.append(
                        {
                            "kind": "checkpoint",
                            "run_id": run_id,
                            "checkpoint_id": str(checkpoint.get("checkpoint_id", uuid4().hex)),
                            "sequence": int(checkpoint.get("sequence", 0) or 0),
                            "phase": str(checkpoint.get("phase", _resolve_phase(run))),
                            "status": str(checkpoint.get("status", run.get("status", "running"))),
                            "metrics_snapshot": checkpoint.get("metrics_snapshot", {}) if isinstance(checkpoint.get("metrics_snapshot"), dict) else {},
                            "active_policy": checkpoint.get("active_policy", {}) if isinstance(checkpoint.get("active_policy"), dict) else {},
                            "current_profile": str(checkpoint.get("current_profile", run.get("profile", "custom"))),
                            "pending_approvals": checkpoint.get("pending_approvals", []) if isinstance(checkpoint.get("pending_approvals"), list) else [],
                            "resume_candidate": bool(checkpoint.get("resume_candidate", False)),
                            "reason": str(checkpoint.get("reason", "")),
                            "current_action": str(checkpoint.get("current_action", "")),
                            "created_at": str(checkpoint.get("created_at", _now_iso())),
                            "ts": str(checkpoint.get("created_at", _now_iso())),
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
                            "phase": _resolve_phase(run),
                            "metrics": metrics,
                            "ts": str(finished_at or _now_iso()),
                        }
                    )

            content = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
            if content:
                content += "\n"
            atomic_write_text(RUNS_FILE, content)
