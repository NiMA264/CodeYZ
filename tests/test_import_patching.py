from __future__ import annotations

from pathlib import Path

from packages.core.patcher import apply_ast_patch
from packages.core.permissions import FILES
from packages.core.project_paths import add_project_path, set_current_project


def _setup_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    add_project_path(str(ws))
    set_current_project(str(ws))
    return ws


def test_add_from_import_handles_multiline_import_block(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    target = ws / "mod.py"
    target.write_text(
        "from os import (\n"
        "    path,\n"
        "    getenv,\n"
        ")\n"
        "\n"
        "def run():\n"
        "    return path.join('a', getenv('HOME', 'b'))\n",
        encoding="utf-8",
    )

    apply_ast_patch(
        "mod.py",
        operation="add_from_import",
        target="os.sep",
        code="from os import sep\n",
        access_level=FILES,
    )

    text = target.read_text(encoding="utf-8")
    assert "from os import sep" in text or "    sep," in text
    assert text.count("sep") == 1
    assert "from os import (" in text
    assert "    path," in text
    assert "    getenv," in text


def test_add_import_is_idempotent_when_alias_import_exists(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    target = ws / "alias_import.py"
    original = (
        "import numpy as np\n"
        "\n"
        "def run():\n"
        "    return np.array([1, 2, 3])\n"
    )
    target.write_text(original, encoding="utf-8")

    apply_ast_patch(
        "alias_import.py",
        operation="add_import",
        target="numpy",
        code="import numpy\n",
        access_level=FILES,
    )

    assert target.read_text(encoding="utf-8") == original


def test_add_from_import_is_idempotent_when_alias_name_exists(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    target = ws / "alias_from_import.py"
    original = (
        "from os import path as p\n"
        "\n"
        "def run():\n"
        "    return p.join('a', 'b')\n"
    )
    target.write_text(original, encoding="utf-8")

    apply_ast_patch(
        "alias_from_import.py",
        operation="add_from_import",
        target="os.path",
        code="from os import path\n",
        access_level=FILES,
    )

    assert target.read_text(encoding="utf-8") == original


def test_add_from_import_preserves_comments_in_import_block(tmp_path: Path) -> None:
    ws = _setup_workspace(tmp_path)
    target = ws / "comments_imports.py"
    target.write_text(
        "# leading comment\n"
        "from os import path  # keep-this-comment\n"
        "\n"
        "def run():\n"
        "    return path.join('a', 'b')\n",
        encoding="utf-8",
    )

    apply_ast_patch(
        "comments_imports.py",
        operation="add_from_import",
        target="os.getenv",
        code="from os import getenv\n",
        access_level=FILES,
    )

    text = target.read_text(encoding="utf-8")
    assert "keep-this-comment" in text
    assert "getenv" in text
    assert text.count("getenv") == 1
