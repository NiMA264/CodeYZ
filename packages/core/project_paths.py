from pathlib import Path

_DEFAULT_PATH = Path(r"F:\Projekte\CodeYZ").resolve()
_ALLOWED_PATHS: set[Path] = {_DEFAULT_PATH}


def _normalize(path: str) -> Path:
    return Path(path).resolve()


def list_allowed_paths() -> list[str]:
    return sorted(str(path) for path in _ALLOWED_PATHS)


def add_allowed_path(path: str) -> str:
    normalized = _normalize(path)
    _ALLOWED_PATHS.add(normalized)
    return str(normalized)


def ensure_allowed_path(path: str) -> Path:
    target = _normalize(path)
    for allowed in _ALLOWED_PATHS:
        allowed_str = str(allowed)
        target_str = str(target)
        if target_str == allowed_str or target_str.startswith(allowed_str + "\\"):
            return target
    raise ValueError("Path is not in allowed project paths")
