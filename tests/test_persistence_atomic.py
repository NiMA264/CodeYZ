from __future__ import annotations

import json
from pathlib import Path

from packages.core.persistence import atomic_write_text


def test_atomic_write_text_replaces_file_content(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_text(target, json.dumps({"a": 1}))
    atomic_write_text(target, json.dumps({"a": 2}))
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["a"] == 2


def test_atomic_write_text_cleans_temp_files(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_text(target, '{"ok": true}')
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".state.json.") and p.suffix == ".tmp"]
    assert leftovers == []
