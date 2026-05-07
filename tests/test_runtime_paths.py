from __future__ import annotations

from pathlib import Path

from packages.core.runtime_paths import ensure_runtime_dirs, get_user_config_root


def test_runtime_root_isolated_to_workspace() -> None:
    root = get_user_config_root()
    workspace = Path(__file__).resolve().parents[1]
    assert root.is_relative_to(workspace)


def test_runtime_directories_created() -> None:
    paths = ensure_runtime_dirs()
    assert paths["root"].exists()
    assert paths["logs"].exists()
    assert paths["runs"].exists()
    assert paths["snapshots"].exists()
    assert paths["diffs"].exists()
