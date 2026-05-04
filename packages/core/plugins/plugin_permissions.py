from __future__ import annotations

from packages.core.permissions import can_run_tests, can_write_files

READ_FILES = "read_files"
WRITE_FILES = "write_files"
RUN_TESTS = "run_tests"
HTTP = "http"
SHELL = "shell"

ALLOWED_PLUGIN_SCOPES = {READ_FILES, WRITE_FILES, RUN_TESTS, HTTP, SHELL}


def validate_plugin_permissions(permissions: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in permissions:
        if item not in ALLOWED_PLUGIN_SCOPES:
            raise ValueError(f"Unsupported plugin permission: {item}")
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


def enforce_plugin_permissions(permissions: list[str], access_level: str | None) -> None:
    if WRITE_FILES in permissions and not can_write_files(access_level):
        raise PermissionError("Plugin permission denied: write_files requires 'Dateien ändern' or 'Autonom'")
    if RUN_TESTS in permissions and not can_run_tests(access_level):
        raise PermissionError("Plugin permission denied: run_tests requires 'Tests ausführen' or 'Autonom'")
    if SHELL in permissions and not can_run_tests(access_level):
        raise PermissionError("Plugin permission denied: shell requires 'Tests ausführen' or 'Autonom'")
