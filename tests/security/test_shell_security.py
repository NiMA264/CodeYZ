from __future__ import annotations

from pathlib import Path

import pytest

from packages.tools.shell import assert_safe_command, run_shell


@pytest.mark.parametrize(
    "command",
    [
        "python -c \"print('ok')\" && git status",
        "python -c \"print('ok')\" | git status",
        "python -c \"print('ok')\"; git status",
        "python -c \"print('ok')\" > out.txt",
    ],
)
def test_shell_injection_tokens_rejected(command: str) -> None:
    with pytest.raises(ValueError):
        assert_safe_command(command)


@pytest.mark.parametrize(
    "command",
    [
        "cmd /c dir",
        "powershell -Command Get-ChildItem",
        "bash -c ls",
        "sh -c ls",
        "npm test",
    ],
)
def test_disallowed_commands_rejected(command: str) -> None:
    with pytest.raises(ValueError):
        run_shell(command)


def test_timeout_handling() -> None:
    with pytest.raises(TimeoutError):
        run_shell("python -c \"__import__('time').sleep(2)\"", timeout=1)


def test_cwd_outside_workspace_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_shell("python -c \"print('ok')\"", cwd=str(tmp_path / ".." / ".."))
