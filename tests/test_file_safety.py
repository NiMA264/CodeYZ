import pytest

from packages.core.project_paths import add_project_path, set_current_project
from packages.tools.files import list_files, safe_path


def test_env_path_blocked() -> None:
    with pytest.raises(ValueError):
        safe_path(".env")


def test_venv_traversal_blocked() -> None:
    with pytest.raises(ValueError):
        safe_path(".venv/whatever.txt")


def test_outside_workspace_blocked() -> None:
    with pytest.raises(ValueError):
        safe_path("../../outside.txt")


def test_path_in_other_allowed_project_blocked(tmp_path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    add_project_path(str(a))
    add_project_path(str(b))
    set_current_project(str(a))
    with pytest.raises(ValueError):
        safe_path(str((b / "x.txt").resolve()))


def test_list_files_excludes_blocked_names() -> None:
    files = list_files(".")
    assert ".env" not in files
    assert all(".venv" not in f for f in files)
    assert all("node_modules" not in f for f in files)
