from __future__ import annotations

import importlib
import json
from pathlib import Path


def test_sessions_persist_and_reload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import sessions as sessions_module

    sessions = importlib.reload(sessions_module)
    session_id = sessions.create_session()
    sessions.add_message(session_id, "user", "hello")
    sessions.add_message(session_id, "assistant", "world")

    sessions_file = tmp_path / "sessions.json"
    assert sessions_file.exists()
    payload = json.loads(sessions_file.read_text(encoding="utf-8"))
    assert session_id in payload["sessions"]

    sessions_reloaded = importlib.reload(sessions_module)
    sessions_reloaded.initialize_sessions_storage()
    data = sessions_reloaded.get_session(session_id)
    assert len(data) == 2
    assert data[0]["content"] == "hello"


def test_sessions_corrupt_file_is_ignored(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text("{ bad json", encoding="utf-8")

    from packages.core import sessions as sessions_module

    sessions = importlib.reload(sessions_module)
    sessions.initialize_sessions_storage()
    sid = sessions.create_session()
    assert sessions.get_session(sid) == []


def test_automations_persist_and_reload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import automations_store as automations_module

    automations = importlib.reload(automations_module)
    item = automations.create_automation("daily", "check", "0 8 * * *")
    assert item["name"] == "daily"

    file_path = tmp_path / "automations.json"
    assert file_path.exists()

    reloaded = importlib.reload(automations_module)
    reloaded.initialize_automations_storage()
    items = reloaded.list_automations()
    assert any(x["id"] == item["id"] for x in items)


def test_automations_missing_or_corrupt_file_is_robust(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEYZ_RUNTIME_ROOT", str(tmp_path))
    from packages.core import automations_store as automations_module

    missing_reload = importlib.reload(automations_module)
    missing_reload.initialize_automations_storage()
    assert isinstance(missing_reload.list_automations(), list)

    (tmp_path / "automations.json").write_text("not-json", encoding="utf-8")
    corrupt_reload = importlib.reload(automations_module)
    corrupt_reload.initialize_automations_storage()
    assert isinstance(corrupt_reload.list_automations(), list)
