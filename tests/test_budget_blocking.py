import pytest

from packages.core import agent_pipeline


def test_budget_aborts_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_pipeline, "planner", lambda *_a, **_k: {"role": "planner", "model": "gpt-5.5", "output": "p", "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 5.0})
    out = agent_pipeline.run_multi_agent_task("task", access_level="Autonom", model="gpt-5.4-mini", max_cost_usd=0.2)
    assert out["ok"] is False
    assert out["error"] == "Budget exceeded"
