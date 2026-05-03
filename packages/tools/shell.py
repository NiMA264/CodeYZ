import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BLOCKED_PATTERNS = [
    "rm -rf",
    "del /s",
    "format",
    "shutdown",
    "sudo",
    "git push --force",
    "git push",
    "deploy",
    "scp ",
    "ssh ",
]


def _safe_cwd(cwd: str) -> Path:
    target = (PROJECT_ROOT / cwd).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        raise ValueError("Blocked cwd outside project root")
    return target


def _is_pipe_shell_install(lowered: str) -> bool:
    return bool(re.search(r"\b(curl|wget)\b.*\|\s*sh\b", lowered))


def run_shell(command: str, cwd: str = ".", timeout: int = 120) -> str:
    lowered = command.lower()

    if _is_pipe_shell_install(lowered):
        raise ValueError("Blocked dangerous command: curl/wget pipe to sh")

    for pattern in BLOCKED_PATTERNS:
        if pattern in lowered:
            raise ValueError(f"Blocked dangerous command: {pattern}")

    result = subprocess.run(
        command,
        cwd=_safe_cwd(cwd),
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )

    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += "\nSTDERR:\n" + result.stderr

    return output.strip() or f"Command finished with code {result.returncode}"
