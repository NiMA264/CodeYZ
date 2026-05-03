import pytest

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


def test_list_files_excludes_blocked_names() -> None:
    files = list_files(".")
    assert ".env" not in files
    assert all(".venv" not in f for f in files)
    assert all("node_modules" not in f for f in files)
