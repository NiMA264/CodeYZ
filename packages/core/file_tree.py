from pathlib import Path

IGNORED_NAMES = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".env"}


def build_file_tree(root: str, max_depth: int = 4, max_items: int = 300) -> dict:
    root_path = Path(root).resolve()
    counter = {"count": 0}

    def walk(path: Path, depth: int) -> dict:
        node = {
            "name": path.name or str(path),
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
        }

        if not path.is_dir() or depth >= max_depth or counter["count"] >= max_items:
            return node

        children: list[dict] = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception:
            entries = []

        for entry in entries:
            if counter["count"] >= max_items:
                break
            if entry.name in IGNORED_NAMES:
                continue

            counter["count"] += 1
            children.append(walk(entry, depth + 1))

        node["children"] = children
        return node

    return walk(root_path, 0)
