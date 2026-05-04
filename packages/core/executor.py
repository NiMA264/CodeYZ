import os
import subprocess
from pathlib import Path

from packages.core.permissions import assert_can_run_tests
from packages.core.project_paths import get_current_project
from packages.tools.shell import assert_safe_command, run_shell

DOCKER_USE_FLAG = "CODEYZ_USE_DOCKER"
DOCKER_IMAGE_ENV = "CODEYZ_DOCKER_IMAGE"
DOCKER_DEFAULT_IMAGE = "codeyz-local"
_BLOCKED_SECRET_FILES = {".env", ".env.local", ".env.production"}


def _summarize(text: str, max_chars: int = 2000) -> str:
    compact = (text or "").strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars] + "\n...[TRUNCATED]"


def _docker_enabled() -> bool:
    return os.getenv(DOCKER_USE_FLAG, "0") == "1"


def _ensure_no_secret_mount(workspace: Path) -> None:
    for name in _BLOCKED_SECRET_FILES:
        if (workspace / name).exists():
            raise RuntimeError(
                f"Docker execution blocked: secret file '{name}' exists in workspace root. "
                "Use host mode or move secret file outside workspace root."
            )


def _build_docker_command(command: str, workspace: Path) -> list[str]:
    image = os.getenv(DOCKER_IMAGE_ENV, DOCKER_DEFAULT_IMAGE)
    return [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{workspace}:/workspace",
        "-w",
        "/workspace",
        image,
        "sh",
        "-lc",
        command,
    ]


def _run_in_docker(command: str, timeout: int = 120) -> str:
    assert_safe_command(command)
    workspace = Path(get_current_project()).resolve()
    _ensure_no_secret_mount(workspace)
    docker_cmd = _build_docker_command(command, workspace)

    try:
        result = subprocess.run(
            docker_cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Docker execution failed: 'docker' command not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Docker execution timed out after {timeout}s") from exc

    output = ""
    if result.stdout:
        output += result.stdout
    if result.stderr:
        output += "\nSTDERR:\n" + result.stderr

    combined = output.strip() or f"Command finished with code {result.returncode}"
    stderr_lower = (result.stderr or "").lower()
    if "daemon" in stderr_lower and "not running" in stderr_lower:
        raise RuntimeError("Docker execution failed: Docker daemon is not reachable.")

    return combined


def _execute_command(command: str, access_level: str | None = None) -> str:
    _ = access_level
    assert_safe_command(command)
    if _docker_enabled():
        return _run_in_docker(command)
    return run_shell(command)


def run_tests(access_level: str | None = None) -> dict[str, str | bool]:
    assert_can_run_tests(access_level)
    output = _execute_command("py -3.11 -m pytest", access_level=access_level)
    failed = "failed" in output.lower() or "error" in output.lower() or "no module named" in output.lower()
    return {"ok": not failed, "output": _summarize(output)}


def run_build(access_level: str | None = None) -> dict[str, str | bool]:
    assert_can_run_tests(access_level)
    output = _execute_command("py -3.11 -m compileall packages", access_level=access_level)
    failed = "traceback" in output.lower() or "error" in output.lower()
    return {"ok": not failed, "output": _summarize(output)}


def summarize_errors(*chunks: str) -> str:
    merged = "\n\n".join(chunk for chunk in chunks if chunk)
    return _summarize(merged, max_chars=2000)
