import pytest

from packages.core import agent_pipeline


def test_multi_agent_order_and_reviewer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_pipeline, "planner", lambda *_a, **_k: "plan")
    monkeypatch.setattr(agent_pipeline, "coder", lambda *_a, **_k: {"patches": []})
    monkeypatch.setattr(agent_pipeline, "tester", lambda *_a, **_k: "tests ok")
    monkeypatch.setattr(agent_pipeline, "reviewer", lambda *_a, **_k: "review ok")
    monkeypatch.setattr(agent_pipeline, "fixer", lambda *_a, **_k: {"patches": []})
    monkeypatch.setattr(agent_pipeline, "run_build", lambda *_a, **_k: {"ok": True, "output": "ok"})
    monkeypatch.setattr(agent_pipeline, "run_tests", lambda *_a, **_k: {"ok": True, "output": "ok"})

    out = agent_pipeline.run_multi_agent_task("task", access_level="Autonom", model="gpt-5.4-mini")
    assert out["ok"] is True

    roles = [e.get("agent_role") for e in out["events"]]
    assert "planner" in roles
    assert "coder" in roles
    assert "tester" in roles
    assert "reviewer" in roles


def test_multi_agent_max_iterations_and_fixer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_pipeline, "planner", lambda *_a, **_k: "plan")
    monkeypatch.setattr(agent_pipeline, "coder", lambda *_a, **_k: {"patches": []})
    monkeypatch.setattr(agent_pipeline, "tester", lambda *_a, **_k: "tests fail")
    monkeypatch.setattr(agent_pipeline, "reviewer", lambda *_a, **_k: "review")
    monkeypatch.setattr(agent_pipeline, "fixer", lambda *_a, **_k: {"patches": []})
    monkeypatch.setattr(agent_pipeline, "run_build", lambda *_a, **_k: {"ok": False, "output": "err"})
    monkeypatch.setattr(agent_pipeline, "run_tests", lambda *_a, **_k: {"ok": False, "output": "err"})

    out = agent_pipeline.run_multi_agent_task("task", access_level="Autonom", model="gpt-5.4-mini")
    assert out["ok"] is False
    assert len(out["iterations"]) == 3
    assert any(e.get("agent_role") == "fixer" for e in out["events"])
