from pathlib import Path

from packages.cli.setup import check_dependencies, check_environment, check_git


def test_setup_check_runs(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    env = check_environment()
    deps = check_dependencies()
    git = check_git()
    assert env
    assert deps
    assert git


def test_setup_detects_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env = check_environment()
    line = next(item for item in env if "OPENAI_API_KEY gesetzt" in item)
    assert line.startswith("✖")


def test_version_file_exists() -> None:
    version_file = Path("VERSION")
    assert version_file.exists()
    assert version_file.read_text(encoding="utf-8").strip()
