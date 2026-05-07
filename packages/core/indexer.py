from __future__ import annotations

import json
import re
from pathlib import Path

from packages.core.project_paths import ensure_allowed_path, get_current_project
from packages.core.search import rank_files

ALLOWED_EXTS = {".py", ".js", ".ts", ".json", ".md"}
BLOCKED_PARTS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
BLOCKED_NAMES = {".env", ".env.local", ".env.production"}
MAX_FILE_BYTES = 50 * 1024
MAX_CONTENT_CHARS = 2000
INDEX_FILENAME = ".codeyz_index.json"

_INDEX_DATA: dict = {"root_path": "", "items": [], "built_at": ""}

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[^\s\n]+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*[^\s\n]+", re.IGNORECASE),
]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _is_allowed(path: Path) -> bool:
    if path.name in BLOCKED_NAMES:
        return False
    if any(part in BLOCKED_PARTS for part in path.parts):
        return False
    return path.suffix.lower() in ALLOWED_EXTS


def _sanitize(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


_SYMBOL_PATTERN = re.compile(r"\b(?:def|class|function|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)")


def _extract_symbols(text: str) -> list[str]:
    return [m.group(1) for m in _SYMBOL_PATTERN.finditer(text or "")][:50]


def _ensure_within_current_workspace(root: Path) -> None:
    current = Path(get_current_project()).resolve()
    target = Path(ensure_allowed_path(str(root))).resolve()
    if current != target and current not in target.parents:
        raise ValueError("Index root must be current workspace or a subdirectory")


def build_index(root_path: str) -> dict:
    root = Path(root_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Invalid root path")
    _ensure_within_current_workspace(root)

    items: list[dict] = []
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if not _is_allowed(file_path):
            continue
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_BYTES:
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        content = _sanitize(text[:MAX_CONTENT_CHARS])
        rel = file_path.relative_to(root).as_posix()
        items.append(
            {
                "path": rel,
                "filename": file_path.name,
                "content": content,
                "symbols": _extract_symbols(text),
                "tokens_estimate": _estimate_tokens(content),
                "size_bytes": size,
                "modified_ts": float(file_path.stat().st_mtime),
            }
        )

    global _INDEX_DATA
    _INDEX_DATA = {
        "root_path": str(root),
        "items": items,
    }
    return _INDEX_DATA


def save_index(root_path: str | None = None) -> str:
    data = _INDEX_DATA if _INDEX_DATA.get("items") else build_index(root_path or ".")
    index_path = Path(data["root_path"]) / INDEX_FILENAME
    index_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    return str(index_path)


def load_index(root_path: str = ".") -> dict:
    root = Path(root_path).resolve()
    _ensure_within_current_workspace(root)
    index_path = root / INDEX_FILENAME
    if not index_path.exists():
        return {"root_path": str(root), "items": []}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    global _INDEX_DATA
    _INDEX_DATA = data
    return data


def search_files(query: str, top_k: int = 5) -> list[dict]:
    items = _INDEX_DATA.get("items", [])
    ranked = rank_files(items, query)
    return ranked[: max(1, top_k)]


def index_status() -> dict:
    return {
        "root_path": _INDEX_DATA.get("root_path", ""),
        "files_indexed": len(_INDEX_DATA.get("items", [])),
    }
