from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
BLOCKED_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def safe_path(path: str) -> Path:
    target = (PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        raise ValueError("Blocked path outside project root")
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
    results: list[str] = []

    for item in root.rglob("*"):
        rel = item.relative_to(PROJECT_ROOT)
        if any(part in BLOCKED_DIRS for part in rel.parts):
            continue
        if item.name in BLOCKED_NAMES:
            continue
        if item.is_file():
            results.append(str(rel))
        if len(results) >= max_files:
            break

    return results
