from __future__ import annotations

import json
from threading import Lock
from uuid import uuid4

from packages.core.persistence import atomic_write_text
from packages.core.runtime_paths import ensure_runtime_dirs

_AUTOMATIONS: list[dict[str, str]] = []
_LOCK = Lock()


def _automations_file():
    return ensure_runtime_dirs()["root"] / "automations.json"


def _save_automations() -> None:
    payload = {"automations": _AUTOMATIONS}
    atomic_write_text(_automations_file(), json.dumps(payload, ensure_ascii=False, indent=2))


def load_automations() -> None:
    target = _automations_file()
    if not target.exists():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    loaded = data.get("automations", []) if isinstance(data, dict) else []
    if not isinstance(loaded, list):
        return

    normalized: list[dict[str, str]] = []
    for item in loaded:
        if not isinstance(item, dict):
            continue
        aid = item.get("id")
        name = item.get("name")
        prompt = item.get("prompt")
        schedule = item.get("schedule")
        if all(isinstance(x, str) for x in [aid, name, prompt, schedule]):
            normalized.append({"id": aid, "name": name, "prompt": prompt, "schedule": schedule})

    with _LOCK:
        _AUTOMATIONS.clear()
        _AUTOMATIONS.extend(normalized)


def list_automations() -> list[dict[str, str]]:
    with _LOCK:
        return list(_AUTOMATIONS)


def create_automation(name: str, prompt: str, schedule: str) -> dict[str, str]:
    item = {
        "id": uuid4().hex,
        "name": name,
        "prompt": prompt,
        "schedule": schedule,
    }
    with _LOCK:
        _AUTOMATIONS.append(item)
        _save_automations()
    return item


def initialize_automations_storage() -> None:
    load_automations()
