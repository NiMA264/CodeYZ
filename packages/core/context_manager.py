from __future__ import annotations

import re
from pathlib import Path

from packages.core.indexer import search_files
from packages.core.path_security import ensure_no_blocked_parts, ensure_within_root
from packages.core.project_paths import get_current_project
from packages.tools.files import BLOCKED_DIRS, BLOCKED_NAMES

_PINNED_FILES: set[str] = set()
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"OPENAI_API_KEY\s*=\s*[^\s\n]+", re.IGNORECASE),
]


def _sanitize(text: str) -> str:
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    return out


def _validate_relative_path(path: str) -> str:
    rel = path.strip().replace("\\", "/")
    if not rel or rel.startswith("/") or ".." in rel.split("/"):
        raise ValueError("Invalid file path")
    if Path(rel).name in BLOCKED_NAMES:
        raise ValueError("Blocked secret file")
    ensure_no_blocked_parts(Path(rel), BLOCKED_DIRS)

    root = Path(get_current_project()).resolve()
    target = ensure_within_root(root / rel, root)
    if not target.exists() or not target.is_file():
        raise ValueError("File not found")
    return rel


def pin_file(path: str) -> str:
    rel = _validate_relative_path(path)
    _PINNED_FILES.add(rel)
    return rel


def unpin_file(path: str) -> str:
    rel = path.strip().replace("\\", "/")
    _PINNED_FILES.discard(rel)
    return rel


def list_pinned_files() -> list[str]:
    return sorted(_PINNED_FILES)


def _read_rel_file(rel: str, max_chars: int = 3000) -> str:
    root = Path(get_current_project()).resolve()
    target = (root / rel).resolve()
    text = target.read_text(encoding="utf-8")
    text = _sanitize(text)
    if len(text) > max_chars:
        return text[:max_chars] + "\n[TRUNCATED]"
    return text


def build_chat_context(
    selected_file: str | None,
    pinned_files: list[str] | None,
    query: str | None = None,
    max_chars: int = 12000,
) -> str:
    pieces: list[str] = []
    budget = max_chars

    def add_chunk(title: str, body: str) -> None:
        nonlocal budget
        if budget <= 0:
            return
        chunk = f"{title}\n{body}\n"
        if len(chunk) > budget:
            chunk = chunk[:budget]
        pieces.append(chunk)
        budget -= len(chunk)

    if selected_file:
        rel = _validate_relative_path(selected_file)
        content = _read_rel_file(rel)
        add_chunk(f"Selected file: {rel}", content)

    for rel in pinned_files or []:
        validated = _validate_relative_path(rel)
        content = _read_rel_file(validated)
        add_chunk(f"Pinned file: {validated}", content)
        if budget <= 0:
            break

    if query and budget > 0:
        for item in search_files(query, top_k=5):
            rel = str(item.get("path", ""))
            try:
                validated = _validate_relative_path(rel)
            except ValueError:
                continue
            content = _read_rel_file(validated, max_chars=1200)
            add_chunk(f"Relevant file: {validated}", content)
            if budget <= 0:
                break

    text = "\n".join(pieces).strip()
    if len(text) > max_chars:
        return text[:max_chars]
    return text
