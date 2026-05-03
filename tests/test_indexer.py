from pathlib import Path

from packages.core.context_manager import build_chat_context, pin_file, unpin_file
from packages.core.indexer import build_index, search_files
from packages.core.project_paths import add_project_path, set_current_project


def test_build_index_and_search(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("calculator add function", encoding="utf-8")
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-proj-SECRET", encoding="utf-8")

    add_project_path(str(tmp_path))
    set_current_project(str(tmp_path))
    data = build_index(str(tmp_path))
    paths = [item["path"] for item in data["items"]]
    assert "a.py" in paths
    assert "notes.md" in paths
    assert ".env" not in paths

    results = search_files("add", top_k=3)
    assert results
    assert results[0]["path"] in {"a.py", "notes.md"}


def test_context_max_chars_with_relevant_files(tmp_path: Path) -> None:
    (tmp_path / "main.py").write_text("print('hello')\n" * 1000, encoding="utf-8")
    (tmp_path / "util.py").write_text("def util_add(x, y):\n    return x + y\n" * 100, encoding="utf-8")

    add_project_path(str(tmp_path))
    set_current_project(str(tmp_path))
    build_index(str(tmp_path))

    pin_file("util.py")
    context = build_chat_context("main.py", ["util.py"], query="add util", max_chars=1200)
    unpin_file("util.py")

    assert len(context) <= 1200
    assert "Selected file:" in context
