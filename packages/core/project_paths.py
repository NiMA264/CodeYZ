from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_PATH = Path(r"F:\Projekte\CodeYZ").resolve()
_PROJECT_PATHS: set[Path] = set()
_CURRENT_PROJECT_PATH: Path = _DEFAULT_PATH


def _normcase_str(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _normalize(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    return p


def _validate_project_dir(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise ValueError("Project path must exist and be a directory")
    if path.is_symlink():
        raise ValueError("Project path must not be a symlink/junction")


def _is_within(child: Path, parent: Path) -> bool:
    child_norm = _normcase_str(child)
    parent_norm = _normcase_str(parent)
    try:
        common = os.path.commonpath([child_norm, parent_norm])
    except ValueError:
        return False
    return common == parent_norm


def add_project_path(path: str) -> str:
    normalized = _normalize(path)
    _validate_project_dir(normalized)
    _PROJECT_PATHS.add(normalized)
    return str(normalized)


def list_project_paths() -> list[str]:
    return sorted(str(path) for path in _PROJECT_PATHS)


def get_current_project() -> str:
    return str(_CURRENT_PROJECT_PATH)


def set_current_project(path: str) -> str:
    global _CURRENT_PROJECT_PATH
    normalized = _normalize(path)
    _validate_project_dir(normalized)
    norm = _normcase_str(normalized)
    if all(_normcase_str(allowed) != norm for allowed in _PROJECT_PATHS):
        raise ValueError("Path is not in allowed project paths")
    for allowed in _PROJECT_PATHS:
        if _normcase_str(allowed) == norm:
            _CURRENT_PROJECT_PATH = allowed
            break
    return str(_CURRENT_PROJECT_PATH)


def ensure_allowed_path(path: str) -> Path:
    target = _normalize(path)
    for allowed in _PROJECT_PATHS:
        if _is_within(target, allowed):
            return target
    raise ValueError("Path is not in allowed project paths")


# initialize defaults
if _DEFAULT_PATH.exists() and _DEFAULT_PATH.is_dir() and not _DEFAULT_PATH.is_symlink():
    _PROJECT_PATHS.add(_DEFAULT_PATH)
else:
    fallback = Path(__file__).resolve().parents[2]
    _PROJECT_PATHS.add(fallback)
    _CURRENT_PROJECT_PATH = fallback
