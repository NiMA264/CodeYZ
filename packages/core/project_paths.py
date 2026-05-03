from pathlib import Path

_DEFAULT_PATH = Path(r"F:\Projekte\CodeYZ").resolve()
_PROJECT_PATHS: set[Path] = set()
_CURRENT_PROJECT_PATH: Path = _DEFAULT_PATH


def _normalize(path: str) -> Path:
    return Path(path).resolve()


def _validate_project_dir(path: Path) -> None:
    if not path.exists() or not path.is_dir():
        raise ValueError("Project path must exist and be a directory")


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
    if normalized not in _PROJECT_PATHS:
        raise ValueError("Path is not in allowed project paths")
    _CURRENT_PROJECT_PATH = normalized
    return str(_CURRENT_PROJECT_PATH)


def ensure_allowed_path(path: str) -> Path:
    target = _normalize(path)
    for allowed in _PROJECT_PATHS:
        allowed_str = str(allowed)
        target_str = str(target)
        if target_str == allowed_str or target_str.startswith(allowed_str + "\\"):
            return target
    raise ValueError("Path is not in allowed project paths")


# initialize defaults
if _DEFAULT_PATH.exists() and _DEFAULT_PATH.is_dir():
    _PROJECT_PATHS.add(_DEFAULT_PATH)
else:
    # fallback to current file root if default is missing
    fallback = Path(__file__).resolve().parents[2]
    _PROJECT_PATHS.add(fallback)
    _CURRENT_PROJECT_PATH = fallback
