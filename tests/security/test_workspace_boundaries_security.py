from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.path_security import ensure_within_root
from packages.core.project_paths import add_project_path, get_current_project, set_current_project
from packages.tools.files import safe_path


@pytest.fixture(autouse=True)
def _restore_current_project() -> None:
    previous = get_current_project()
    try:
        yield
    finally:
        set_current_project(previous)


def test_path_traversal_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    add_project_path(str(workspace))
    set_current_project(str(workspace))

    with pytest.raises(ValueError):
        safe_path("../outside.txt")


def test_absolute_outside_workspace_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()

    with pytest.raises(ValueError):
        ensure_within_root(outside, workspace)


def test_windows_style_separators_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    add_project_path(str(workspace))
    set_current_project(str(workspace))

    with pytest.raises(ValueError):
        safe_path("..\\..\\outside.txt")


def test_symlink_escape_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("x", encoding="utf-8")
    link = workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported in this environment")

    with pytest.raises(ValueError):
        ensure_within_root(link / "secret.txt", workspace)
