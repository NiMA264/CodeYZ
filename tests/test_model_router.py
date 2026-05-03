import pytest

from packages.core.costs import BudgetCheck, estimate_cost, estimate_tokens
from packages.core.model_router import (
    ALLOWED_MODELS,
    get_model_for_role,
    set_model_for_role,
    validate_model,
)
from packages.core import agent_pipeline


def test_validate_model_ok_and_invalid() -> None:
    assert validate_model("gpt-5.4") == "gpt-5.4"
    with pytest.raises(ValueError):
        validate_model("bad-model")


def test_model_router_get_set() -> None:
    set_model_for_role("planner", "gpt-5.5")
    assert get_model_for_role("planner") in ALLOWED_MODELS


def test_cost_estimation_and_budget() -> None:
    tokens = estimate_tokens("abcd" * 100)
    assert tokens > 0
    meta = estimate_cost("gpt-5.4-mini", "input", "output")
    assert meta["estimated_cost_usd"] >= 0

    budget = BudgetCheck(max_cost_usd=0.001)
    assert budget.can_spend(0.0005)
    budget.spend(0.0005)
    assert not budget.can_spend(0.001)


def test_budget_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_pipeline, "planner", lambda *_a, **_k: {"role": "planner", "model": "gpt-5.5", "output": "p", "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 1.0})
    monkeypatch.setattr(agent_pipeline, "coder", lambda *_a, **_k: {"role": "coder", "model": "gpt-5.4", "output": "{}", "json": {"patches": []}, "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 0.0})
    monkeypatch.setattr(agent_pipeline, "tester", lambda *_a, **_k: {"role": "tester", "model": "gpt-5.4-mini", "output": "ok", "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 0.0})
    monkeypatch.setattr(agent_pipeline, "reviewer", lambda *_a, **_k: {"role": "reviewer", "model": "gpt-5.5", "output": "ok", "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 0.0})
    monkeypatch.setattr(agent_pipeline, "fixer", lambda *_a, **_k: {"role": "fixer", "model": "gpt-5.4", "output": "{}", "json": {"patches": []}, "estimated_input_tokens": 1, "estimated_output_tokens": 1, "estimated_cost_usd": 0.0})
    monkeypatch.setattr(agent_pipeline, "run_build", lambda *_a, **_k: {"ok": True, "output": "ok"})
    monkeypatch.setattr(agent_pipeline, "run_tests", lambda *_a, **_k: {"ok": True, "output": "ok"})

    out = agent_pipeline.run_multi_agent_task("task", access_level="Autonom", model="gpt-5.4-mini", max_cost_usd=0.1)
    assert out["ok"] is False
    assert out["error"] == "Budget exceeded"
