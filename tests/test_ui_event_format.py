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


def test_event_formatter_handles_approval_required_distinctly() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { formatTimelineEvent } from './packages/server/static/event_format.js';
const lines = formatTimelineEvent({
  event_type: 'approval_required',
  agent_role: 'coder',
  title: 'High-risk patch requires approval',
  data: { file: 'a.py', risk_level: 'high', reasons: ['high_deletion_ratio'], stats: { changed_lines: 40 }, patch_preview: '@@ -1,2 +1,0 @@\\\\n-a\\\\n-b' }
});
console.log(JSON.stringify(lines));
"""
    out = _run_node(script, repo)
    lines = json.loads(out)
    joined = "\n".join(lines)
    assert "approval_required" in joined
    assert "risk=high" in joined
    assert "preview=" in joined


def test_event_formatter_keeps_generic_error_format() -> None:
    repo = Path(__file__).resolve().parents[1]
    script = """
import { formatTimelineEvent } from './packages/server/static/event_format.js';
const lines = formatTimelineEvent({
  event_type: 'error',
  agent_role: 'coder',
  title: 'Patch failed',
  data: { error: 'parse failed' }
});
console.log(JSON.stringify(lines));
"""
    out = _run_node(script, repo)
    lines = json.loads(out)
    assert lines[0].startswith("- [error]")
