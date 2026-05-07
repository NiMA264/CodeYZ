from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

PluginHandler = Callable[[dict[str, Any] | None], Any]

_REGISTRY: dict[str, dict[str, Any]] = {}


def register_plugin(plugin: dict[str, Any]) -> None:
    name = str(plugin.get("name", "")).strip()
    if not name:
        raise ValueError("Plugin name is required")
    existing = _REGISTRY.get(name, {})
    merged = dict(existing)
    merged.update(plugin)
    merged.setdefault("enabled", True)
    _REGISTRY[name] = merged


def list_plugins() -> list[dict[str, Any]]:
    items = [deepcopy(item) for item in _REGISTRY.values()]
    items.sort(key=lambda x: str(x.get("name", "")))
    for item in items:
        item.pop("handler", None)
    return items


def get_plugin(name: str) -> dict[str, Any] | None:
    plugin = _REGISTRY.get(name)
    if plugin is None:
        return None
    cleaned = deepcopy(plugin)
    cleaned.pop("handler", None)
    return cleaned


def enable_plugin(name: str) -> None:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown plugin: {name}")
    _REGISTRY[name]["enabled"] = True


def disable_plugin(name: str) -> None:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown plugin: {name}")
    _REGISTRY[name]["enabled"] = False


def call_plugin(name: str, input_data: dict[str, Any] | None = None, access_level: str | None = None) -> Any:
    from packages.core.plugins.plugin_permissions import enforce_plugin_permissions
    from packages.core.plugins.subprocess_exec import execute_plugin_subprocess

    plugin = _REGISTRY.get(name)
    if plugin is None:
        raise ValueError(f"Unknown plugin: {name}")
    if not bool(plugin.get("enabled", False)):
        raise PermissionError(f"Plugin is disabled: {name}")
    handler = plugin.get("handler")
    if not callable(handler):
        raise ValueError(f"Plugin has no callable handler: {name}")
    permissions = plugin.get("permissions", [])
    if not isinstance(permissions, list):
        permissions = []
    enforce_plugin_permissions([str(p) for p in permissions], access_level)
    if str(plugin.get("execution_mode", "inprocess")) == "subprocess":
        return execute_plugin_subprocess(plugin, input_data or {})
    return handler(input_data or {})
