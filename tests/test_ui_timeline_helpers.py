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
  { event_id: '2', event_type: 'approval_required', data: { file: 'b.py', risk_level: 'high', patch_preview: '@@', patch: { file_path: 'b.py', unified_diff: '@@' } } },
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
