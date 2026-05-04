from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.permissions import TESTS


def test_build_docker_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from packages.core import executor

    monkeypatch.setenv("CODEYZ_DOCKER_IMAGE", "codeyz-test")
    cmd = executor._build_docker_command("py -3.11 -m pytest", tmp_path)  # type: ignore[attr-defined]
    assert cmd[0] == "docker"
    assert "--privileged" not in cmd
    assert "codeyz-test" in cmd
    assert f"{tmp_path}:/workspace" in cmd


def test_host_fallback_when_docker_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.delenv("CODEYZ_USE_DOCKER", raising=False)
    monkeypatch.setattr(executor, "run_shell", lambda command: f"host:{command}")
    out = executor.run_build(access_level=TESTS)
    assert out["ok"] is True
    assert "host:py -3.11 -m compileall packages" in str(out["output"])


def test_docker_mode_blocks_workspace_secret_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from packages.core import executor

    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test", encoding="utf-8")
    monkeypatch.setenv("CODEYZ_USE_DOCKER", "1")
    monkeypatch.setattr(executor, "get_current_project", lambda: str(tmp_path))
    with pytest.raises(RuntimeError):
        executor.run_tests(access_level=TESTS)


def test_host_mode_keeps_blocked_command_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.delenv("CODEYZ_USE_DOCKER", raising=False)
    monkeypatch.setattr(executor, "run_shell", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("Blocked dangerous command")))
    with pytest.raises(ValueError):
        executor._execute_command("rm -rf /tmp/x", access_level=TESTS)  # type: ignore[attr-defined]


def test_executor_docker_mode_also_blocks_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.setenv("CODEYZ_USE_DOCKER", "1")
    with pytest.raises(ValueError):
        executor._execute_command("git push origin main", access_level=TESTS)  # type: ignore[attr-defined]


def test_executor_allows_safe_commands_with_mocked_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from packages.core import executor

    monkeypatch.delenv("CODEYZ_USE_DOCKER", raising=False)
    monkeypatch.setattr(executor, "run_shell", lambda command: f"ok:{command}")
    out = executor._execute_command("py -3.11 -m compileall packages", access_level=TESTS)  # type: ignore[attr-defined]
    assert out == "ok:py -3.11 -m compileall packages"
