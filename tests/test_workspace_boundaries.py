from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.project_paths import (
    add_project_path,
    ensure_allowed_path,
    set_current_project,
)


def test_traversal_blocked_for_allowed_boundary(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    add_project_path(str(workspace))
    set_current_project(str(workspace))

    outside = tmp_path / "outside.txt"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError):
        ensure_allowed_path(str(outside))


def test_other_drive_or_disjoint_path_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    add_project_path(str(workspace))

    disjoint = tmp_path.parent / "disjoint-folder"
    disjoint.mkdir(exist_ok=True)
    with pytest.raises(ValueError):
        ensure_allowed_path(str(disjoint))


def test_symlink_workspace_blocked_if_supported(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink not supported in this environment")

    with pytest.raises(ValueError):
        add_project_path(str(link))
