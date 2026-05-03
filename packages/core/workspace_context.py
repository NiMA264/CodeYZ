from packages.tools.files import list_files, read_file

IMPORTANT_FILES = ["README.md", "AGENTS.md", "pyproject.toml", "package.json"]


def _safe_read(path: str, max_chars: int = 1500) -> str:
    try:
        return read_file(path, max_chars=max_chars)
    except Exception:
        return ""


def build_workspace_context(max_files: int = 120, max_chars: int = 8000) -> str:
    files = list_files(".", max_files=max_files)
    py_files = [f for f in files if f.startswith("packages/") and f.endswith(".py")]

    chunks: list[str] = []
    chunks.append("Workspace summary:")
    chunks.append("Important files:")

    for path in IMPORTANT_FILES:
        if path in files:
            content = _safe_read(path)
            if content:
                chunks.append(f"\nFILE: {path}\n{content}")

    if py_files:
        chunks.append("\nPython files (packages/**/*.py):")
        chunks.append("\n".join(py_files[:max_files]))

    text = "\n".join(chunks).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text
