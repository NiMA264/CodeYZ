from datetime import datetime
from difflib import unified_diff
from pathlib import Path

from packages.tools.files import PROJECT_ROOT, safe_path

DIFF_ARCHIVE_DIR = PROJECT_ROOT / ".codeyz_diffs"


def apply_patch(file_path: str, new_content: str) -> dict[str, str]:
    target = safe_path(file_path)
    old_content = ""
    if target.exists():
        old_content = target.read_text(encoding="utf-8")

    diff_text = "\n".join(
        unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )

    DIFF_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    sanitized = file_path.replace("/", "_").replace("\\", "_")
    archive_name = f"{stamp}_{sanitized}.diff"
    (DIFF_ARCHIVE_DIR / archive_name).write_text(diff_text, encoding="utf-8")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new_content, encoding="utf-8")

    return {
        "file": file_path,
        "diff": diff_text,
        "archive": str(Path(".codeyz_diffs") / archive_name),
    }
