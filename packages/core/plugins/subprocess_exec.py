from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_PLUGIN_IO_CHARS = 20000
PLUGIN_TIMEOUT_SECONDS = 5


def _truncate(text: str) -> str:
    if len(text) <= MAX_PLUGIN_IO_CHARS:
        return text
    return text[:MAX_PLUGIN_IO_CHARS]


def execute_plugin_subprocess(plugin: dict[str, Any], input_data: dict[str, Any] | None = None) -> Any:
    entry_path = Path(str(plugin.get("entry_path", ""))).resolve()
    plugin_dir = Path(str(plugin.get("plugin_dir", ""))).resolve()
    if not entry_path.exists():
        raise ValueError("Plugin entry path missing")
    if not plugin_dir.exists():
        raise ValueError("Plugin directory missing")

    payload = json.dumps(input_data or {}, ensure_ascii=True)
    cmd = [
        sys.executable,
        "-m",
        "packages.core.plugins.subprocess_worker",
        str(entry_path),
        payload,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=plugin_dir,
            shell=False,
            text=True,
            capture_output=True,
            timeout=PLUGIN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Plugin execution timed out") from exc

    out = _truncate(proc.stdout or "")
    err = _truncate(proc.stderr or "")
    if proc.returncode != 0:
        raise ValueError(f"Plugin subprocess failed ({proc.returncode}): {err or out or 'unknown_error'}")
    if not out.strip():
        raise ValueError("Plugin subprocess returned empty output")
    try:
        return json.loads(out.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("Plugin subprocess returned invalid JSON") from exc
