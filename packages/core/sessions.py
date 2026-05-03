from threading import Lock
from uuid import uuid4

_SESSIONS: dict[str, list[dict[str, str]]] = {}
_LOCK = Lock()


def create_session() -> str:
    session_id = uuid4().hex
    with _LOCK:
        _SESSIONS[session_id] = []
    return session_id


def add_message(session_id: str, role: str, content: str) -> None:
    with _LOCK:
        if session_id not in _SESSIONS:
            _SESSIONS[session_id] = []
        _SESSIONS[session_id].append({"role": role, "content": content})


def get_session(session_id: str) -> list[dict[str, str]]:
    with _LOCK:
        return list(_SESSIONS.get(session_id, []))
