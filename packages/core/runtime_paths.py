from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "CodeYZ"


def get_user_config_root() -> Path:
    base = os.getenv("APPDATA")
    if base:
        root = Path(base) / APP_NAME
    else:
        root = Path.home() / f".{APP_NAME.lower()}"
    root.mkdir(parents=True, exist_ok=True)
    return root


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

