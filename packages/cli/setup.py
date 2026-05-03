from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

from packages.core.runtime_paths import get_env_file_path


def _status(ok: bool, label: str, detail: str = "") -> str:
    encoding = (sys.stdout.encoding or "").lower()
    ascii_only = not encoding or "utf" not in encoding
    if ascii_only:
        mark = "[OK]" if ok else "[FAIL]"
    else:
        mark = "✔" if ok else "✖"
    tail = f" - {detail}" if detail else ""
    return f"{mark} {label}{tail}"


def check_environment() -> list[str]:
    lines: list[str] = []
    py_ok = sys.version_info >= (3, 11)
    lines.append(_status(py_ok, "Python >= 3.11", sys.version.split()[0]))

    local_env = Path(".env")
    app_env = get_env_file_path()
    env_ok = local_env.exists() or app_env.exists()
    lines.append(_status(env_ok, ".env vorhanden", f"local={local_env.exists()} appdata={app_env.exists()}"))

    key_ok = bool(os.getenv("OPENAI_API_KEY"))
    lines.append(_status(key_ok, "OPENAI_API_KEY gesetzt"))

    venv_ok = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    lines.append(_status(venv_ok, "Virtuelle Umgebung aktiv", sys.prefix))
    return lines


def check_dependencies() -> list[str]:
    frozen = bool(getattr(sys, "frozen", False))
    required = ["openai", "fastapi", "typer", "rich", "uvicorn"]
    if not frozen:
        required.append("pytest")

    lines: list[str] = []
    for mod in required:
        try:
            importlib.import_module(mod)
            lines.append(_status(True, f"Dependency {mod}"))
        except Exception:
            lines.append(_status(False, f"Dependency {mod}", "nicht importierbar"))
    return lines


def check_git() -> list[str]:
    lines: list[str] = []
    try:
        version = subprocess.check_output(["git", "--version"], text=True, stderr=subprocess.STDOUT).strip()
        lines.append(_status(True, "Git installiert", version))
    except Exception:
        lines.append(_status(False, "Git installiert", "git nicht gefunden"))
        return lines

    try:
        _ = subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], text=True, stderr=subprocess.STDOUT).strip()
        lines.append(_status(True, "Git Repository erkannt"))
    except Exception:
        lines.append(_status(False, "Git Repository erkannt", "kein git worktree"))
    return lines
