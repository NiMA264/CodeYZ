from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.patcher import PatchApprovalRequired, apply_unified_diff, assess_patch_risk
from packages.core.permissions import FILES
from packages.core.project_paths import add_project_path, set_current_project


def test_apply_unified_diff_small_hunk(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    add_project_path(str(ws))
    set_current_project(str(ws))

    target = ws / "a.txt"
    target.write_text("line1\nline2\nline3\n", encoding="utf-8")
    diff_text = "@@ -1,3 +1,3 @@\n line1\n-line2\n+line2-updated\n line3"

    out = apply_unified_diff("a.txt", diff_text, access_level=FILES)
    assert out["file"] == "a.txt"
    assert out["risk_level"] == "low"
    assert "line2-updated" in target.read_text(encoding="utf-8")


def test_apply_unified_diff_context_mismatch_no_partial_write(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    add_project_path(str(ws))
    set_current_project(str(ws))

    target = ws / "b.txt"
    original = "alpha\nbeta\ngamma\n"
    target.write_text(original, encoding="utf-8")
    bad_diff = "@@ -1,3 +1,3 @@\n alpha\n-WRONG\n+beta-updated\n gamma"

    with pytest.raises(ValueError):
        apply_unified_diff("b.txt", bad_diff, access_level=FILES)
    assert target.read_text(encoding="utf-8") == original


def test_apply_unified_diff_outside_current_project_blocked(tmp_path: Path) -> None:
    ws_a = tmp_path / "a"
    ws_b = tmp_path / "b"
    ws_a.mkdir()
    ws_b.mkdir()
    add_project_path(str(ws_a))
    add_project_path(str(ws_b))
    set_current_project(str(ws_a))

    target_outside = ws_b / "c.txt"
    target_outside.write_text("x\n", encoding="utf-8")
    diff_text = "@@ -1,1 +1,1 @@\n-x\n+y"

    with pytest.raises(ValueError):
        apply_unified_diff(str(target_outside), diff_text, access_level=FILES)


def test_assess_patch_risk_small_patch_low() -> None:
    diff_text = "@@ -1,2 +1,2 @@\n a\n-b\n+b2"
    risk = assess_patch_risk("src/a.py", diff_text)
    assert risk["level"] == "low"


def test_assess_patch_risk_many_deletions_high() -> None:
    deletions = "\n".join([f"-line{i}" for i in range(35)])
    diff_text = f"@@ -1,35 +1,0 @@\n{deletions}"
    risk = assess_patch_risk("src/a.py", diff_text)
    assert risk["level"] == "high"


def test_assess_patch_risk_sensitive_file_medium_or_higher() -> None:
    diff_text = "@@ -1,1 +1,1 @@\n-a\n+b"
    risk = assess_patch_risk("AGENTS.md", diff_text)
    assert risk["level"] in {"medium", "high"}


def test_high_risk_blocked_without_approval(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    add_project_path(str(ws))
    set_current_project(str(ws))

    target = ws / "d.txt"
    target.write_text("".join([f"line{i}\\n" for i in range(40)]), encoding="utf-8")
    diff_text = "@@ -1,40 +1,0 @@\n" + "\n".join([f"-line{i}" for i in range(40)])

    with pytest.raises(PatchApprovalRequired) as exc:
        apply_unified_diff("d.txt", diff_text, access_level=FILES)
    assert exc.value.risk_level == "high"
    assert exc.value.file_path == "d.txt"


def test_high_risk_allowed_with_approval(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    add_project_path(str(ws))
    set_current_project(str(ws))

    target = ws / "e.txt"
    target.write_text("".join([f"line{i}\n" for i in range(40)]), encoding="utf-8")
    diff_text = "@@ -1,40 +1,0 @@\n" + "\n".join([f"-line{i}" for i in range(40)])

    out = apply_unified_diff("e.txt", diff_text, access_level=FILES, approved=True)
    assert out["risk_level"] == "high"
    assert target.read_text(encoding="utf-8").strip() == ""
