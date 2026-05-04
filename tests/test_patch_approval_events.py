import pytest

from packages.core import agent_loop, agent_pipeline
from packages.core.patcher import PatchApprovalRequired


def test_agent_loop_emits_approval_required_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_loop,
        "_plan_and_patch",
        lambda *_a, **_k: {
            "plan": "x",
            "patches": [{"file_path": "a.py", "unified_diff": "@@ -1,1 +1,1 @@\n-a\n+b"}],
        },
    )
    monkeypatch.setattr(
        agent_loop,
        "apply_unified_diff",
        lambda *_a, **_k: (_ for _ in ()).throw(
            PatchApprovalRequired("a.py", "high", ["high_deletion_ratio"], {"changed_lines": 40}, "@@ ...")
        ),
    )
    monkeypatch.setattr(agent_loop, "run_build", lambda *_a, **_k: {"ok": True, "output": "ok"})
    monkeypatch.setattr(agent_loop, "run_tests", lambda *_a, **_k: {"ok": True, "output": "ok"})

    out = agent_loop.run_autonomous_task("task", access_level="Autonom", model="gpt-5.4-mini")
    events = out["events"]
    assert any(e["event_type"] == "approval_required" for e in events)


def test_pipeline_emits_approval_required_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_pipeline, "planner", lambda *_a, **_k: "plan")
    monkeypatch.setattr(agent_pipeline, "coder", lambda *_a, **_k: {"patches": [{"file_path": "x.py", "unified_diff": "@@ -1,1 +1,1 @@\n-a\n+b"}]})
    monkeypatch.setattr(agent_pipeline, "tester", lambda *_a, **_k: "tests ok")
    monkeypatch.setattr(agent_pipeline, "reviewer", lambda *_a, **_k: "review ok")
    monkeypatch.setattr(agent_pipeline, "fixer", lambda *_a, **_k: {"patches": []})
    monkeypatch.setattr(
        agent_pipeline,
        "apply_unified_diff",
        lambda *_a, **_k: (_ for _ in ()).throw(
            PatchApprovalRequired("x.py", "high", ["large_change_set"], {"changed_lines": 120}, "@@ ...")
        ),
    )
    monkeypatch.setattr(agent_pipeline, "run_build", lambda *_a, **_k: {"ok": True, "output": "ok"})
    monkeypatch.setattr(agent_pipeline, "run_tests", lambda *_a, **_k: {"ok": True, "output": "ok"})

    out = agent_pipeline.run_multi_agent_task("task", access_level="Autonom", model="gpt-5.4-mini")
    assert any(e["event_type"] == "approval_required" for e in out["events"])


def test_agent_loop_keeps_normal_patch_errors_as_error_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        agent_loop,
        "_plan_and_patch",
        lambda *_a, **_k: {
            "plan": "x",
            "patches": [{"file_path": "a.py", "unified_diff": "@@ -1,1 +1,1 @@\n-a\n+b"}],
        },
    )
    monkeypatch.setattr(
        agent_loop,
        "apply_unified_diff",
        lambda *_a, **_k: (_ for _ in ()).throw(ValueError("generic patch parse error")),
    )
    monkeypatch.setattr(agent_loop, "run_build", lambda *_a, **_k: {"ok": True, "output": "ok"})
    monkeypatch.setattr(agent_loop, "run_tests", lambda *_a, **_k: {"ok": True, "output": "ok"})

    out = agent_loop.run_autonomous_task("task", access_level="Autonom", model="gpt-5.4-mini")
    events = out["events"]
    assert any(e["event_type"] == "error" for e in events)
    assert not any(e["event_type"] == "approval_required" for e in events)
