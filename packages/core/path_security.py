from __future__ import annotations

from pathlib import Path


def resolve_canonical(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def ensure_within_root(target: str | Path, root: str | Path) -> Path:
    resolved_target = resolve_canonical(target)
    resolved_root = resolve_canonical(root)
    if not resolved_target.is_relative_to(resolved_root):
        raise ValueError("Path is outside allowed root")
    return resolved_target


def ensure_no_blocked_parts(path: str | Path, blocked_parts: set[str]) -> None:
    parts = {part.lower() for part in Path(path).parts}
    blocked = {part.lower() for part in blocked_parts}
    if parts.intersection(blocked):
        raise ValueError("Blocked directory")
