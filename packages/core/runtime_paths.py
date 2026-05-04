from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "CodeYZ"
FALLBACK_ROOT = Path(__file__).resolve().parents[2] / ".codeyz_runtime"


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def get_user_config_root() -> Path:
    explicit = os.getenv("CODEYZ_RUNTIME_ROOT")
    if explicit:
        root = Path(explicit).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    base = os.getenv("APPDATA")
    if base:
        candidate = Path(base) / APP_NAME
        if _is_writable_dir(candidate):
            return candidate

    if _is_writable_dir(FALLBACK_ROOT):
        return FALLBACK_ROOT

    home_fallback = Path.home() / f".{APP_NAME.lower()}"
    home_fallback.mkdir(parents=True, exist_ok=True)
    return home_fallback


def ensure_runtime_dirs() -> dict[str, Path]:
    root = get_user_config_root()
    paths = {
        "root": root,
        "logs": root / "logs",
        "runs": root / "runs",
        "snapshots": root / "snapshots",
        "diffs": root / "diffs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def get_env_file_path() -> Path:
    return get_user_config_root() / ".env"
