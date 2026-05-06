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
