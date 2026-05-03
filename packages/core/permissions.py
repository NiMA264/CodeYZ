from __future__ import annotations

READ_ONLY = "Nur lesen"
FILES = "Dateien ändern"
TESTS = "Tests ausführen"
AUTONOMOUS = "Autonom"

_ALLOWED = {READ_ONLY, FILES, TESTS, AUTONOMOUS}


class AccessDeniedError(PermissionError):
    pass


def normalize_access_level(access_level: str | None) -> str:
    if access_level in _ALLOWED:
        return access_level
    return READ_ONLY


def can_read_files(access_level: str | None) -> bool:
    return normalize_access_level(access_level) in {READ_ONLY, FILES, TESTS, AUTONOMOUS}


def can_write_files(access_level: str | None) -> bool:
    return normalize_access_level(access_level) in {FILES, AUTONOMOUS}


def can_run_tests(access_level: str | None) -> bool:
    return normalize_access_level(access_level) in {TESTS, AUTONOMOUS}


def can_run_autonomous(access_level: str | None) -> bool:
    return normalize_access_level(access_level) == AUTONOMOUS


def assert_can_write_files(access_level: str | None) -> None:
    if not can_write_files(access_level):
        raise AccessDeniedError("Access denied: writing files requires 'Dateien ändern' or 'Autonom'")


def assert_can_run_tests(access_level: str | None) -> None:
    if not can_run_tests(access_level):
        raise AccessDeniedError("Access denied: running tests requires 'Tests ausführen' or 'Autonom'")


def assert_can_run_autonomous(access_level: str | None) -> None:
    if not can_run_autonomous(access_level):
        raise AccessDeniedError("Access denied: autonomous mode requires 'Autonom'")
