from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from packages.core.plugins.plugin_permissions import validate_plugin_permissions
from packages.core.plugins.plugin_registry import register_plugin

REQUIRED_FIELDS = {"name", "description", "version", "permissions", "entry", "functions"}
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_PARTS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}


def _safe_plugin_path(base: Path, target: Path) -> Path:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    if not str(resolved_target).startswith(str(resolved_base)):
        raise ValueError("Plugin path outside plugin root")
    if resolved_target.name in BLOCKED_NAMES:
        raise ValueError("Blocked file")
    if any(part in BLOCKED_PARTS for part in resolved_target.parts):
        raise ValueError("Blocked directory")
    return resolved_target


def _load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Manifest missing fields: {sorted(missing)}")
    if not isinstance(data["functions"], list) or not data["functions"]:
        raise ValueError("Manifest functions must be a non-empty list")
    if "run" not in data["functions"]:
        raise ValueError("Manifest must include function 'run'")
    data["permissions"] = validate_plugin_permissions([str(p) for p in data["permissions"]])
    return data


def _load_handler(plugin_dir: Path, entry: str):
    entry_path = _safe_plugin_path(plugin_dir, plugin_dir / entry)
    if entry_path.suffix != ".py":
        raise ValueError("Plugin entry must be a .py file")
    spec = importlib.util.spec_from_file_location(f"codeyz_plugin_{plugin_dir.name}", entry_path)
    if spec is None or spec.loader is None:
        raise ValueError("Could not load plugin module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = getattr(module, "run", None)
    if not callable(handler):
        raise ValueError("Plugin entry must define callable run(input_data)")
    return handler


def load_plugins(directory: str | Path) -> list[dict[str, Any]]:
    root = Path(directory).resolve()
    if not root.exists() or not root.is_dir():
        return []

    loaded: list[dict[str, Any]] = []
    for plugin_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        try:
            safe_dir = _safe_plugin_path(root, plugin_dir)
            manifest_path = _safe_plugin_path(safe_dir, safe_dir / "manifest.json")
            if not manifest_path.exists():
                continue
            manifest = _load_manifest(manifest_path)
            handler = _load_handler(safe_dir, str(manifest["entry"]))
            plugin = {
                "name": str(manifest["name"]),
                "description": str(manifest["description"]),
                "version": str(manifest["version"]),
                "permissions": manifest["permissions"],
                "functions": manifest["functions"],
                "entry": str(manifest["entry"]),
                "enabled": True,
                "handler": handler,
            }
            register_plugin(plugin)
            loaded.append({k: v for k, v in plugin.items() if k != "handler"})
        except Exception:
            continue

    return loaded
