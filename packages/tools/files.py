from pathlib import Path

from packages.core.project_paths import ensure_allowed_path, get_current_project

BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def safe_path(path: str) -> Path:
    root = Path(get_current_project()).resolve()
    target = (root / path).resolve()
    ensure_allowed_path(str(target))
    if target.name in BLOCKED_NAMES:
        raise ValueError("Blocked secret file")
    if any(part in BLOCKED_DIRS for part in target.parts):
        raise ValueError("Blocked directory")
    return target


def read_file(path: str, max_chars: int = 12000) -> str:
    target = safe_path(path)
    text = target.read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


def write_file(path: str, content: str) -> str:
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"written: {path}"


def list_files(path: str = ".", max_files: int = 300) -> list[str]:
    root = safe_path(path)
    current_root = Path(get_current_project()).resolve()
    results: list[str] = []

    for item in root.rglob("*"):
        rel = item.relative_to(current_root)
        if any(part in BLOCKED_DIRS for part in rel.parts):
            continue
        if item.name in BLOCKED_NAMES:
            continue
        if item.is_file():
            results.append(str(rel))
        if len(results) >= max_files:
            break

    return results
