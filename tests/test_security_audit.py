from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.context_manager import build_chat_context, pin_file, unpin_file
from packages.core.indexer import MAX_FILE_BYTES, build_index
from packages.core.project_paths import add_project_path, set_current_project


def test_indexer_blocks_env_and_large_files(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    add_project_path(str(workspace))
    set_current_project(str(workspace))

    (workspace / "ok.py").write_text("print('ok')", encoding="utf-8")
    (workspace / ".env").write_text("OPENAI_API_KEY=sk-test-secret", encoding="utf-8")
    (workspace / "big.md").write_text("x" * (MAX_FILE_BYTES + 20), encoding="utf-8")

    data = build_index(str(workspace))
    paths = {item["path"] for item in data["items"]}
    assert "ok.py" in paths
    assert ".env" not in paths
    assert "big.md" not in paths


def test_indexer_outside_current_workspace_blocked(tmp_path: Path) -> None:
    ws_a = tmp_path / "a"
    ws_b = tmp_path / "b"
    ws_a.mkdir()
    ws_b.mkdir()
    add_project_path(str(ws_a))
    add_project_path(str(ws_b))
    set_current_project(str(ws_a))

    with pytest.raises(ValueError):
        build_index(str(ws_b))


def test_context_secret_redaction_and_max_chars(tmp_path: Path) -> None:
    workspace = tmp_path / "ctx"
    workspace.mkdir()
    add_project_path(str(workspace))
    set_current_project(str(workspace))

    target = workspace / "file.py"
    target.write_text("OPENAI_API_KEY=sk-super-secret\nprint('ok')\n" * 20, encoding="utf-8")
    pin_file("file.py")
    context = build_chat_context("file.py", ["file.py"], max_chars=250)
    unpin_file("file.py")

    assert len(context) <= 250
    assert "sk-super-secret" not in context
    assert "[REDACTED]" in context
