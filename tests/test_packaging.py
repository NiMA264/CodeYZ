from pathlib import Path

from packages.core.runtime_paths import ensure_runtime_dirs


def test_packaging_assets_exist() -> None:
    assert Path("VERSION").exists()
    assert Path("packages/server/static/index.html").exists()
    assert Path("packages/server/static/app.js").exists()


def test_config_path_exists() -> None:
    dirs = ensure_runtime_dirs()
    assert dirs["root"].exists()
    assert dirs["logs"].exists()
