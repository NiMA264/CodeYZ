from datetime import datetime
from difflib import unified_diff
from pathlib import Path

from packages.core.ast_patcher import apply_ast_patch_text
from packages.core.permissions import assert_can_write_files
from packages.core.rollback import create_rollback_record
from packages.core.runtime_paths import ensure_runtime_dirs
from packages.tools.files import safe_path

DIFF_ARCHIVE_DIR = ensure_runtime_dirs()["diffs"]
SENSITIVE_NAMES = {"AGENTS.md", "pyproject.toml", "package.json"}
SENSITIVE_PARTS = {".github", "docker", "installer"}


class PatchApprovalRequired(PermissionError):
    def __init__(
        self,
        file_path: str,
        risk_level: str,
        reasons: list[str],
        stats: dict[str, object],
        patch_text: str = "",
    ) -> None:
        self.file_path = file_path
        self.risk_level = risk_level
        self.reasons = reasons
        self.stats = stats
        self.patch_text = patch_text
        super().__init__(f"High-risk patch requires explicit approval (approved=True). Reasons: {', '.join(reasons)}")


def _build_diff(file_path: str, old_content: str, new_content: str) -> str:
    return "\n".join(
        unified_diff(
            old_content.splitlines(),
            new_content.splitlines(),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )
    )


def _archive_and_write(file_path: str, target: Path, old_content: str, new_content: str) -> dict[str, str]:
    diff_text = _build_diff(file_path, old_content, new_content)

    rollback = create_rollback_record(
        file_path=file_path,
        before_content=old_content,
        after_content=new_content,
        diff=diff_text,
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
        "archive": str(Path("diffs") / archive_name),
        "rollback_id": rollback["rollback_id"],
    }


def _parse_hunk_header(header: str) -> tuple[int, int, int, int]:
    parts = header.strip().split(" ")
    if len(parts) < 3:
        raise ValueError("Invalid hunk header")

    old_part = parts[1]
    new_part = parts[2]
    if not old_part.startswith("-") or not new_part.startswith("+"):
        raise ValueError("Invalid hunk header")

    def _parse(part: str) -> tuple[int, int]:
        raw = part[1:]
        if "," in raw:
            start_raw, count_raw = raw.split(",", 1)
            return int(start_raw), int(count_raw)
        return int(raw), 1

    old_start, old_count = _parse(old_part)
    new_start, new_count = _parse(new_part)
    return old_start, old_count, new_start, new_count


def _apply_unified_diff_text(old_content: str, unified_diff_text: str) -> str:
    lines = unified_diff_text.splitlines()
    hunks: list[tuple[int, list[str]]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@"):
            old_start, _old_count, _new_start, _new_count = _parse_hunk_header(line)
            i += 1
            hunk_lines: list[str] = []
            while i < len(lines) and not lines[i].startswith("@@"):
                hunk_lines.append(lines[i])
                i += 1
            hunks.append((old_start, hunk_lines))
            continue
        i += 1

    if not hunks:
        raise ValueError("No hunks found in unified diff")

    old_lines = old_content.splitlines()
    new_lines: list[str] = []
    old_pos = 0

    for old_start, hunk_lines in hunks:
        target_idx = max(old_start - 1, 0)
        if target_idx < old_pos:
            raise ValueError("Overlapping or out-of-order hunks")

        new_lines.extend(old_lines[old_pos:target_idx])
        cursor = target_idx

        for entry in hunk_lines:
            if not entry:
                raise ValueError("Invalid empty hunk line")
            tag = entry[0]
            body = entry[1:]
            if tag == " ":
                if cursor >= len(old_lines) or old_lines[cursor] != body:
                    raise ValueError("Hunk context does not match file")
                new_lines.append(old_lines[cursor])
                cursor += 1
            elif tag == "-":
                if cursor >= len(old_lines) or old_lines[cursor] != body:
                    raise ValueError("Hunk delete line does not match file")
                cursor += 1
            elif tag == "+":
                new_lines.append(body)
            elif tag == "\\":
                continue
            else:
                raise ValueError("Unsupported unified diff line")

        old_pos = cursor

    new_lines.extend(old_lines[old_pos:])
    result = "\n".join(new_lines)
    if old_content.endswith("\n"):
        result += "\n"
    return result


def assess_patch_risk(file_path: str, patch_text: str, *, is_new_file: bool = False) -> dict[str, object]:
    additions = 0
    deletions = 0
    for line in (patch_text or "").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1

    changed = additions + deletions
    deletion_ratio = (deletions / changed) if changed else 0.0

    reasons: list[str] = []
    level = "low"

    path_obj = Path(file_path)
    if path_obj.name in SENSITIVE_NAMES or any(part in SENSITIVE_PARTS for part in path_obj.parts):
        level = "medium"
        reasons.append("sensitive_path")

    if is_new_file:
        if level == "low":
            level = "medium"
        reasons.append("new_file")

    if changed > 80:
        level = "high"
        reasons.append("large_change_set")

    if deletions >= 30 or (changed >= 10 and deletion_ratio >= 0.7):
        level = "high"
        reasons.append("high_deletion_ratio")

    if changed <= 12 and deletions <= 4 and level == "low":
        reasons.append("small_patch")

    return {
        "level": level,
        "reasons": reasons,
        "stats": {
            "changed_lines": changed,
            "additions": additions,
            "deletions": deletions,
            "deletion_ratio": round(deletion_ratio, 3),
            "is_new_file": is_new_file,
        },
    }


def _enforce_risk_policy(risk: dict[str, object], approved: bool) -> None:
    if str(risk.get("level", "low")) == "high" and not approved:
        raise PatchApprovalRequired(
            file_path="",
            risk_level=str(risk.get("level", "high")),
            reasons=[str(x) for x in risk.get("reasons", [])],
            stats=risk.get("stats", {}) if isinstance(risk.get("stats", {}), dict) else {},
        )


def apply_patch(
    file_path: str,
    new_content: str,
    access_level: str | None = None,
    approved: bool = False,
) -> dict[str, str]:
    assert_can_write_files(access_level)

    target = safe_path(file_path)
    old_content = ""
    exists_before = target.exists()
    if exists_before:
        old_content = target.read_text(encoding="utf-8")

    diff_text = _build_diff(file_path, old_content, new_content)
    risk = assess_patch_risk(file_path, diff_text, is_new_file=not exists_before)
    try:
        _enforce_risk_policy(risk, approved=approved)
    except PatchApprovalRequired as exc:
        exc.file_path = file_path
        exc.patch_text = diff_text
        raise

    out = _archive_and_write(file_path, target, old_content, new_content)
    out["risk_level"] = str(risk["level"])
    return out


def apply_unified_diff(
    file_path: str,
    unified_diff: str,
    access_level: str | None = None,
    approved: bool = False,
) -> dict[str, str]:
    assert_can_write_files(access_level)

    if not unified_diff.strip():
        raise ValueError("Unified diff is empty")

    target = safe_path(file_path)
    old_content = ""
    exists_before = target.exists()
    if exists_before:
        old_content = target.read_text(encoding="utf-8")

    risk = assess_patch_risk(file_path, unified_diff, is_new_file=not exists_before)
    try:
        _enforce_risk_policy(risk, approved=approved)
    except PatchApprovalRequired as exc:
        exc.file_path = file_path
        exc.patch_text = unified_diff
        raise

    new_content = _apply_unified_diff_text(old_content, unified_diff)
    out = _archive_and_write(file_path, target, old_content, new_content)
    out["risk_level"] = str(risk["level"])
    return out


def apply_ast_patch(
    file_path: str,
    operation: str,
    target: str,
    code: str,
    access_level: str | None = None,
    approved: bool = False,
) -> dict[str, str]:
    assert_can_write_files(access_level)
    if not file_path.endswith(".py"):
        raise ValueError("ast_patch currently supports Python files only")

    target_path = safe_path(file_path)
    old_content = ""
    exists_before = target_path.exists()
    if exists_before:
        old_content = target_path.read_text(encoding="utf-8")

    new_content = apply_ast_patch_text(old_content, operation=operation, target=target, code=code)
    diff_text = _build_diff(file_path, old_content, new_content)
    risk = assess_patch_risk(file_path, diff_text, is_new_file=not exists_before)
    try:
        _enforce_risk_policy(risk, approved=approved)
    except PatchApprovalRequired as exc:
        exc.file_path = file_path
        exc.patch_text = diff_text
        raise

    out = _archive_and_write(file_path, target_path, old_content, new_content)
    out["risk_level"] = str(risk["level"])
    return out
