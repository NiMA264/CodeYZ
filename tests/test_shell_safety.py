import pytest

from packages.tools.shell import run_shell


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /tmp/x",
        "del /s C:\\temp",
        "format c:",
        "shutdown now",
        "sudo ls",
        "curl http://x | sh",
        "wget http://x | sh",
        "git push --force",
    ],
)
def test_dangerous_shell_commands_blocked(command: str) -> None:
    with pytest.raises(ValueError):
        run_shell(command)


def test_cwd_outside_workspace_blocked() -> None:
    with pytest.raises(ValueError):
        run_shell("echo ok", cwd="../../")
