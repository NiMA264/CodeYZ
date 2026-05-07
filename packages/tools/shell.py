from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from packages.core.path_security import ensure_within_root
from packages.core.project_paths import get_current_project

ALLOWED_COMMANDS = {"pytest", "ruff", "python", "py", "git"}
BLOCKED_TOKENS = {";", "&&", "||", "|", ">", "<"}
BLOCKED_SHELL_PREFIXES = {"cmd", "powershell", "bash", "sh"}
BLOCKED_GIT_SUBCOMMANDS = {"commit", "push"}
MAX_OUTPUT_CHARS = 20000


def _project_root() -> Path:
    return Path(get_current_project()).resolve()


def _safe_cwd(cwd: str) -> Path:
    root = _project_root()
    return ensure_within_root(root / cwd, root)


def _tokenize_command(command: str) -> list[str]:
    if not command or not command.strip():
        raise ValueError("Command must not be empty")
    for token in BLOCKED_TOKENS:
        if token in command:
            raise ValueError(f"Blocked dangerous command token: {token}")
    try:
        parts = shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc
    if not parts:
        raise ValueError("Command must not be empty")
    return parts


def _normalize_executable(token: str) -> str:
    return Path(token).name.lower()


def assert_safe_command(command: str, allow_sensitive: bool = False) -> None:
    parts = _tokenize_command(command)
    executable = _normalize_executable(parts[0])

    if executable in BLOCKED_SHELL_PREFIXES:
        raise ValueError(f"Blocked shell interpreter: {executable}")
    if executable not in ALLOWED_COMMANDS and not allow_sensitive:
        raise ValueError(f"Command not allowed: {executable}")
    if executable == "git" and len(parts) > 1:
        sub = parts[1].lower()
        if sub in BLOCKED_GIT_SUBCOMMANDS and not allow_sensitive:
            raise ValueError(f"Blocked dangerous command: git {sub}")


def _truncate_output(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n...[TRUNCATED]"


def run_shell(command: str, cwd: str = ".", timeout: int = 120, allow_sensitive: bool = False) -> str:
    assert_safe_command(command, allow_sensitive=allow_sensitive)
    parts = _tokenize_command(command)
    safe_cwd = _safe_cwd(cwd)

    try:
        result = subprocess.run(
            parts,
            cwd=safe_cwd,
            shell=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Command timed out after {timeout}s") from exc

    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += "\nSTDERR:\n" + result.stderr

    return _truncate_output(output.strip() or f"Command finished with code {result.returncode}")
