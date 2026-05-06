from __future__ import annotations

from datetime import datetime, timezone

RISK_ORDER = {"low": 1, "medium": 2, "high": 3}

DEFAULT_POLICY: dict[str, object] = {
    "max_files_changed": 5,
    "max_added_lines": 240,
    "max_removed_lines": 120,
    "allow_shell": True,
    "allow_delete": False,
    "allow_rename": False,
    "require_approval": True,
    "require_tests": True,
    "allow_multi_agent": True,
    "max_risk_level": "medium",
    "max_runtime_minutes": 10,
}

PROFILE_POLICIES: dict[str, dict[str, object]] = {
    "review": {
        "max_files_changed": 3,
        "max_added_lines": 120,
        "max_removed_lines": 60,
        "allow_shell": False,
        "allow_delete": False,
        "allow_rename": False,
        "require_approval": True,
        "require_tests": False,
        "allow_multi_agent": False,
        "max_risk_level": "low",
        "max_runtime_minutes": 6,
    },
    "safe_mode": {
        "max_files_changed": 2,
        "max_added_lines": 80,
        "max_removed_lines": 30,
        "allow_shell": False,
        "allow_delete": False,
        "allow_rename": False,
        "require_approval": True,
        "require_tests": False,
        "allow_multi_agent": False,
        "max_risk_level": "low",
        "max_runtime_minutes": 5,
    },
    "fast_fix": {
        "max_files_changed": 4,
        "max_added_lines": 220,
        "max_removed_lines": 100,
        "allow_shell": True,
        "allow_delete": False,
        "allow_rename": False,
        "require_approval": False,
        "require_tests": True,
        "allow_multi_agent": False,
        "max_risk_level": "medium",
        "max_runtime_minutes": 12,
    },
    "autonomous": {
        "max_files_changed": 8,
        "max_added_lines": 500,
        "max_removed_lines": 260,
        "allow_shell": True,
        "allow_delete": False,
        "allow_rename": False,
        "require_approval": False,
        "require_tests": True,
        "allow_multi_agent": True,
        "max_risk_level": "high",
        "max_runtime_minutes": 25,
    },
}


def _as_int(value: object, fallback: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except Exception:
        return fallback
    return max(n, 0)


def _as_bool(value: object, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return fallback


def normalize_policy(raw: dict[str, object] | None) -> dict[str, object]:
    src = raw or {}
    risk = str(src.get("max_risk_level", DEFAULT_POLICY["max_risk_level"])).lower()
    if risk not in RISK_ORDER:
        risk = str(DEFAULT_POLICY["max_risk_level"])
    return {
        "max_files_changed": _as_int(src.get("max_files_changed"), int(DEFAULT_POLICY["max_files_changed"])),
        "max_added_lines": _as_int(src.get("max_added_lines"), int(DEFAULT_POLICY["max_added_lines"])),
        "max_removed_lines": _as_int(src.get("max_removed_lines"), int(DEFAULT_POLICY["max_removed_lines"])),
        "allow_shell": _as_bool(src.get("allow_shell"), bool(DEFAULT_POLICY["allow_shell"])),
        "allow_delete": _as_bool(src.get("allow_delete"), bool(DEFAULT_POLICY["allow_delete"])),
        "allow_rename": _as_bool(src.get("allow_rename"), bool(DEFAULT_POLICY["allow_rename"])),
        "require_approval": _as_bool(src.get("require_approval"), bool(DEFAULT_POLICY["require_approval"])),
        "require_tests": _as_bool(src.get("require_tests"), bool(DEFAULT_POLICY["require_tests"])),
        "allow_multi_agent": _as_bool(src.get("allow_multi_agent"), bool(DEFAULT_POLICY["allow_multi_agent"])),
        "max_risk_level": risk,
        "max_runtime_minutes": _as_int(src.get("max_runtime_minutes"), int(DEFAULT_POLICY["max_runtime_minutes"])),
    }


def resolve_policy(profile: str | None, overrides: dict[str, object] | None = None) -> dict[str, object]:
    base = dict(DEFAULT_POLICY)
    profile_key = str(profile or "custom").strip().lower()
    profile_policy = PROFILE_POLICIES.get(profile_key, {})
    base.update(profile_policy)
    if isinstance(overrides, dict):
        base.update(overrides)
    return normalize_policy(base)


def risk_exceeds(max_risk_level: str, risk_level: str) -> bool:
    max_score = RISK_ORDER.get(str(max_risk_level or "").lower(), RISK_ORDER["medium"])
    risk_score = RISK_ORDER.get(str(risk_level or "").lower(), RISK_ORDER["low"])
    return risk_score > max_score


def runtime_exceeded(created_at_iso: str | None, max_runtime_minutes: int) -> bool:
    if not created_at_iso:
        return False
    try:
        created = datetime.fromisoformat(str(created_at_iso))
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    elapsed_minutes = (now - created).total_seconds() / 60.0
    return elapsed_minutes > max(float(max_runtime_minutes), 0.0)


def evaluate_constraints(
    *,
    policy: dict[str, object] | None,
    metrics: dict[str, object] | None = None,
    run_state: dict[str, object] | None = None,
    patch_meta: dict[str, object] | None = None,
    runtime: dict[str, object] | None = None,
    action: str = "general",
) -> dict[str, object]:
    effective = normalize_policy(policy if isinstance(policy, dict) else {})
    m = metrics if isinstance(metrics, dict) else {}
    rs = run_state if isinstance(run_state, dict) else {}
    pm = patch_meta if isinstance(patch_meta, dict) else {}
    rt = runtime if isinstance(runtime, dict) else {}

    checks: list[dict[str, object]] = []
    reasons: list[str] = []

    def _add_check(name: str, severity: str, message: str, triggered: bool, details: dict[str, object] | None = None) -> None:
        checks.append(
            {
                "constraint": name,
                "severity": severity,
                "message": message[:220],
                "triggered": bool(triggered),
                "details": details or {},
            }
        )
        if triggered:
            reasons.append(name)

    files_changed = int(m.get("files_changed_count") or 0)
    added_lines = int(m.get("added_lines") or 0)
    removed_lines = int(m.get("removed_lines") or 0)
    risk_level = str(pm.get("risk_level") or m.get("risk_level_summary") or "unknown").lower()
    file_status = str(pm.get("file_status") or "unknown").lower()
    wants_shell = bool(rt.get("wants_shell", False))
    wants_multi_agent = bool(rt.get("wants_multi_agent", False))
    wants_tests = bool(rt.get("wants_tests", False))
    tests_ok = bool(rt.get("tests_ok", False))
    created_at = str(rs.get("created_at") or "")

    _add_check(
        "max_files_changed",
        "blocked",
        "Maximum changed files exceeded",
        files_changed > int(effective["max_files_changed"]),
        {"value": files_changed, "limit": int(effective["max_files_changed"])},
    )
    _add_check(
        "max_added_lines",
        "approval_required",
        "Maximum added lines exceeded",
        added_lines > int(effective["max_added_lines"]),
        {"value": added_lines, "limit": int(effective["max_added_lines"])},
    )
    _add_check(
        "max_removed_lines",
        "approval_required",
        "Maximum removed lines exceeded",
        removed_lines > int(effective["max_removed_lines"]),
        {"value": removed_lines, "limit": int(effective["max_removed_lines"])},
    )
    _add_check(
        "allow_delete",
        "blocked",
        "Deletes are blocked by policy",
        file_status == "deleted" and not bool(effective["allow_delete"]),
        {"file_status": file_status},
    )
    _add_check(
        "allow_rename",
        "blocked",
        "Renames are blocked by policy",
        file_status == "renamed" and not bool(effective["allow_rename"]),
        {"file_status": file_status},
    )
    _add_check(
        "allow_shell",
        "warning",
        "Shell execution is disabled by policy",
        wants_shell and not bool(effective["allow_shell"]),
    )
    _add_check(
        "allow_multi_agent",
        "blocked",
        "Multi-agent mode is disabled by policy",
        wants_multi_agent and not bool(effective["allow_multi_agent"]),
    )
    _add_check(
        "max_risk_level",
        "approval_required",
        "Risk level exceeds policy",
        risk_level in RISK_ORDER and risk_exceeds(str(effective["max_risk_level"]), risk_level),
        {"risk_level": risk_level, "max": str(effective["max_risk_level"])},
    )
    _add_check(
        "require_approval",
        "approval_required",
        "Policy requires explicit approval",
        action == "patch" and bool(effective["require_approval"]),
    )
    _add_check(
        "require_tests",
        "approval_required",
        "Policy requires passing tests",
        wants_tests and bool(effective["require_tests"]) and not tests_ok,
    )
    _add_check(
        "max_runtime_minutes",
        "blocked",
        "Runtime limit exceeded",
        runtime_exceeded(created_at, int(effective["max_runtime_minutes"])),
        {"limit_minutes": int(effective["max_runtime_minutes"])},
    )

    blocked = any(bool(c["triggered"]) and c["severity"] == "blocked" for c in checks)
    requires_approval = any(bool(c["triggered"]) and c["severity"] == "approval_required" for c in checks)
    warnings = [c for c in checks if bool(c["triggered"]) and c["severity"] == "warning"]
    violations = [c for c in checks if bool(c["triggered"]) and c["severity"] in {"blocked", "approval_required"}]

    return {
        "action": action,
        "blocked": blocked,
        "requires_approval": requires_approval and not blocked,
        "warnings": warnings,
        "violations": violations,
        "reasons": sorted(set(reasons)),
        "risk_level": risk_level,
        "triggered_constraints": [c["constraint"] for c in checks if bool(c["triggered"])],
        "checks": checks,
        "severity": "blocked" if blocked else ("approval_required" if requires_approval else ("warning" if warnings else "info")),
        "policy": effective,
    }
