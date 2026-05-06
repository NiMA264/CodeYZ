from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def _run_node(js_source: str, cwd: Path) -> str:
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        ["node", "--input-type=module", "-e", js_source],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def test_extract_approval_actions_only_for_approval_required() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { extractApprovalActions } from './packages/server/static/timeline_helpers.js';
const actions = extractApprovalActions([
  { event_id: '1', event_type: 'error', data: { file: 'a.py', patch: { file_path: 'a.py', unified_diff: '@@' } } },
  { event_id: '2', event_type: 'approval_required', data: { file: 'b.py', risk_level: 'high', patch_preview: '@@', patch: { file_path: 'b.py', unified_diff: '@@' }, files_changed_count: 2, added_lines: 4, removed_lines: 1, hunks_count: 1 } },
  { event_id: '4', event_type: 'approval_applied', data: { source_event_id: '2' } },
  { event_id: '3', event_type: 'approval_required', data: { file: 'c.py' } }
]);
console.log(JSON.stringify(actions));
"""
    out = _run_node(script, repo)
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["eventId"] == "2"
    assert data[0]["file"] == "b.py"
    assert data[0]["alreadyApplied"] is True
    assert data[0]["buttonLabel"] == "Already applied"
    assert data[0]["filesChangedCount"] == 2


def test_parse_unified_diff_returns_hunks_with_line_types() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { parseUnifiedDiff } from './packages/server/static/timeline_helpers.js';
const hunks = parseUnifiedDiff(`@@ -1,3 +1,4 @@
 line1
-line2
+line2b
+line2c
 line3`);
console.log(JSON.stringify(hunks));
"""
    out = _run_node(script, repo)
    data = json.loads(out)
    assert len(data) == 1
    types = [line["type"] for line in data[0]["lines"]]
    assert "context" in types
    assert "removed" in types
    assert "added" in types


def test_collect_diff_files_from_events_builds_multi_file_list() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { collectDiffFilesFromEvents } from './packages/server/static/timeline_helpers.js';
const files = collectDiffFilesFromEvents([
  { event_type: 'diff', data: { file: 'a.py', diff: `@@ -1,1 +1,1 @@
-a
+b` } },
  { event_type: 'approval_required', event_id: 'evt-2', data: { file: 'b.py', stats: { is_new_file: true }, patch: { file_path: 'b.py', unified_diff: `@@ -0,0 +1,1 @@
+new` } } }
]);
console.log(JSON.stringify(files));
"""
    out = _run_node(script, repo)
    data = json.loads(out)
    assert len(data) == 2
    assert {item["file"] for item in data} == {"a.py", "b.py"}
    status_by_file = {item["file"]: item["status"] for item in data}
    assert status_by_file["b.py"] == "added"


def test_collect_diff_files_prefers_explicit_metadata_status() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { collectDiffFilesFromEvents } from './packages/server/static/timeline_helpers.js';
const files = collectDiffFilesFromEvents([
  { event_type: 'diff', data: { file: 'c.py', file_status: 'deleted', added_lines: 0, removed_lines: 4, hunks_count: 1, diff: `@@ -1,4 +0,0 @@
-a
-b
-c
-d` } }
]);
console.log(JSON.stringify(files));
"""
    out = _run_node(script, repo)
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["status"] == "deleted"
    assert data[0]["removedLines"] == 4
