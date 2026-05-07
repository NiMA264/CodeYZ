from __future__ import annotations

import importlib.util
import json
import logging
import os
import hashlib
from pathlib import Path
from typing import Any

from packages.core.path_security import ensure_no_blocked_parts, ensure_within_root
from packages.core.plugins.plugin_permissions import validate_plugin_permissions
from packages.core.plugins.plugin_registry import register_plugin

REQUIRED_FIELDS = {"name", "description", "version", "permissions", "entry", "functions"}
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_PARTS = {".git", ".venv", "node_modules", "__pycache__", "dist", "build"}
TRUSTED_HASHES_ENV = "CODEYZ_TRUSTED_PLUGIN_HASHES_FILE"
DEFAULT_TRUSTED_HASH_FILE = "trusted_plugins.json"

logger = logging.getLogger(__name__)
_LAST_PLUGIN_LOAD_ERRORS: list[str] = []


def _safe_plugin_path(base: Path, target: Path) -> Path:
    resolved_target = ensure_within_root(target, base)
    if resolved_target.name in BLOCKED_NAMES:
        raise ValueError("Blocked file")
    ensure_no_blocked_parts(resolved_target, BLOCKED_PARTS)
    return resolved_target


def _trusted_hashes_path(root: Path) -> Path:
    explicit = os.getenv(TRUSTED_HASHES_ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    return root / DEFAULT_TRUSTED_HASH_FILE


def _load_trusted_hashes(root: Path) -> dict[str, str]:
    target = _trusted_hashes_path(root)
    if not target.exists():
        return {}
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Trusted plugin hashes file must contain a JSON object")
    cleaned: dict[str, str] = {}
    for name, digest in data.items():
        if not isinstance(name, str) or not isinstance(digest, str):
            continue
        cleaned[name] = digest.strip().lower()
    return cleaned


def _hash_plugin_files(plugin_dir: Path, manifest_path: Path, entry_path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(manifest_path.read_bytes())
    digest.update(entry_path.read_bytes())
    digest.update(plugin_dir.name.encode("utf-8"))
    return digest.hexdigest()


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
    _LAST_PLUGIN_LOAD_ERRORS.clear()
    root = Path(directory).resolve()
    if not root.exists() or not root.is_dir():
        return []
    trusted_hashes_file = _trusted_hashes_path(root)
    try:
        trusted_hashes = _load_trusted_hashes(root)
    except ValueError as exc:
        message = f"Plugin trust config invalid: {exc}"
        _LAST_PLUGIN_LOAD_ERRORS.append(message)
        logger.error(message)
        raise
    enforce_hashes = trusted_hashes_file.exists()

    loaded: list[dict[str, Any]] = []
    for plugin_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        try:
            safe_dir = _safe_plugin_path(root, plugin_dir)
            manifest_path = _safe_plugin_path(safe_dir, safe_dir / "manifest.json")
            if not manifest_path.exists():
                continue
            manifest = _load_manifest(manifest_path)
            entry_path = _safe_plugin_path(safe_dir, safe_dir / str(manifest["entry"]))
            plugin_hash = _hash_plugin_files(safe_dir, manifest_path, entry_path)
            expected_hash = trusted_hashes.get(str(manifest["name"]))
            if enforce_hashes:
                if not expected_hash:
                    logger.warning("Plugin rejected: missing trusted hash for %s", manifest["name"])
                    _LAST_PLUGIN_LOAD_ERRORS.append(f"Plugin rejected (missing hash): {manifest['name']}")
                    continue
                if expected_hash != plugin_hash:
                    logger.warning("Plugin rejected: hash mismatch for %s", manifest["name"])
                    _LAST_PLUGIN_LOAD_ERRORS.append(f"Plugin rejected (hash mismatch): {manifest['name']}")
                    continue
            handler = _load_handler(safe_dir, str(manifest["entry"]))
            plugin = {
                "name": str(manifest["name"]),
                "description": str(manifest["description"]),
                "version": str(manifest["version"]),
                "permissions": manifest["permissions"],
                "functions": manifest["functions"],
                "entry": str(manifest["entry"]),
                "entry_path": str(entry_path),
                "plugin_dir": str(safe_dir),
                "execution_mode": "subprocess" if enforce_hashes else "inprocess",
                "enabled": True,
                "handler": handler,
            }
            register_plugin(plugin)
            loaded.append({k: v for k, v in plugin.items() if k != "handler"})
            logger.info("Plugin loaded: %s", manifest["name"])
        except Exception:
            logger.exception("Plugin load failed for directory: %s", plugin_dir.name)
            _LAST_PLUGIN_LOAD_ERRORS.append(f"Plugin load failed: {plugin_dir.name}")
            continue

    return loaded


def get_last_plugin_load_errors() -> list[str]:
    return list(_LAST_PLUGIN_LOAD_ERRORS)
