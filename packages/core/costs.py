from __future__ import annotations

from dataclasses import dataclass

PRICES_PER_1M = {
    "gpt-5.5": {"input": 5.00, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_text: str, output_text: str) -> dict:
    price = PRICES_PER_1M.get(model, PRICES_PER_1M["gpt-5.4-mini"])
    in_tok = estimate_tokens(input_text)
    out_tok = estimate_tokens(output_text)
    cost = (in_tok / 1_000_000) * price["input"] + (out_tok / 1_000_000) * price["output"]
    return {
        "estimated_input_tokens": in_tok,
        "estimated_output_tokens": out_tok,
        "estimated_cost_usd": round(cost, 6),
    }


@dataclass
class BudgetCheck:
    max_cost_usd: float
    current_cost_usd: float = 0.0

    def can_spend(self, estimated_cost: float) -> bool:
        return (self.current_cost_usd + estimated_cost) <= self.max_cost_usd

    def spend(self, estimated_cost: float) -> None:
        self.current_cost_usd += estimated_cost
