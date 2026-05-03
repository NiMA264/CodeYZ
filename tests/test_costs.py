from packages.core.costs import estimate_cost, estimate_tokens


def test_estimate_tokens_simple() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("x" * 400) >= 100


def test_estimate_cost_structure() -> None:
    meta = estimate_cost("gpt-5.4", "hello", "world")
    assert "estimated_input_tokens" in meta
    assert "estimated_output_tokens" in meta
    assert "estimated_cost_usd" in meta
