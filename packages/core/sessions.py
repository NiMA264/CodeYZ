import json
from threading import Lock
from uuid import uuid4

from packages.core.persistence import atomic_write_text
from packages.core.runtime_paths import ensure_runtime_dirs

_SESSIONS: dict[str, list[dict[str, str]]] = {}
_LOCK = Lock()


def _sessions_file():
    return ensure_runtime_dirs()["root"] / "sessions.json"


def _save_sessions() -> None:
    payload = {"sessions": _SESSIONS}
    atomic_write_text(_sessions_file(), json.dumps(payload, ensure_ascii=False, indent=2))


def load_sessions() -> None:
    target = _sessions_file()
    if not target.exists():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    loaded = data.get("sessions", {}) if isinstance(data, dict) else {}
    if not isinstance(loaded, dict):
        return

    normalized: dict[str, list[dict[str, str]]] = {}
    for sid, messages in loaded.items():
        if not isinstance(sid, str) or not isinstance(messages, list):
            continue
        cleaned: list[dict[str, str]] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if isinstance(role, str) and isinstance(content, str):
                cleaned.append({"role": role, "content": content})
        normalized[sid] = cleaned

    with _LOCK:
        _SESSIONS.clear()
        _SESSIONS.update(normalized)


def create_session() -> str:
    session_id = uuid4().hex
    with _LOCK:
        _SESSIONS[session_id] = []
        _save_sessions()
    return session_id


def add_message(session_id: str, role: str, content: str) -> None:
    with _LOCK:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = []
        _SESSIONS[session_id].append({"role": role, "content": content})
        _save_sessions()


def get_session(session_id: str) -> list[dict[str, str]]:
    with _LOCK:
        return list(_SESSIONS.get(session_id, []))


def initialize_sessions_storage() -> None:
    load_sessions()
