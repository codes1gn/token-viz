"""Pricing table and cost estimation for token-viz."""
import json
import os
from typing import Optional

PRICING_TABLE = {
    "claude-sonnet-4.6":  {"in": 3.00,  "out": 15.00},
    "claude-sonnet-4.5":  {"in": 3.00,  "out": 15.00},
    "claude-haiku-4.5":   {"in": 0.25,  "out": 1.25},
    "claude-haiku-4":     {"in": 0.25,  "out": 1.25},
    "claude-opus-4":      {"in": 15.00, "out": 75.00},
    "claude-opus-4.7":    {"in": 15.00, "out": 75.00},
    "gpt-4o":             {"in": 5.00,  "out": 15.00},
    "gpt-4o-mini":        {"in": 0.15,  "out": 0.60},
    "gpt-4.1":            {"in": 2.00,  "out": 8.00},
    "gpt-5-mini":         {"in": 0.40,  "out": 1.60},
    "gpt-5.4-mini":       {"in": 0.40,  "out": 1.60},
    "gpt-5.2":            {"in": 7.50,  "out": 30.00},
    "gpt-5.3-codex":      {"in": 3.00,  "out": 15.00},
    "gpt-5.4":            {"in": 7.50,  "out": 30.00},
    # unit: USD per 1,000,000 tokens (MTok)
}

_CUSTOM_PRICING_PATH = os.path.expanduser("~/.config/token-viz/pricing.json")


def load_pricing() -> dict:
    """Load pricing table, merging custom overrides if present."""
    table = dict(PRICING_TABLE)
    if os.path.exists(_CUSTOM_PRICING_PATH):
        try:
            with open(_CUSTOM_PRICING_PATH, encoding="utf-8") as f:
                custom = json.load(f)
            table.update(custom)
        except Exception:
            pass
    return table


def get_prices(model: str, table: Optional[dict] = None) -> Optional[dict]:
    """Return {in, out} USD/MTok for a model, or None if unknown."""
    if table is None:
        table = load_pricing()
    # Exact match first
    if model in table:
        return table[model]
    # Prefix match (e.g. "claude-sonnet-4.6-20250101" -> "claude-sonnet-4.6")
    for key in table:
        if model.startswith(key) or key.startswith(model):
            return table[key]
    return None


def estimate_cost(input_tokens: int, output_tokens: int, model: str,
                  table: Optional[dict] = None) -> float:
    """Return estimated cost in USD. Returns -1.0 if model unknown."""
    prices = get_prices(model, table)
    if prices is None:
        return -1.0
    cost = (input_tokens / 1_000_000) * prices["in"]
    cost += (output_tokens / 1_000_000) * prices["out"]
    return round(cost, 6)


def format_cost(cost_usd: float) -> str:
    """Format cost as readable string with $ sign."""
    if cost_usd < 0:
        return "unknown"
    if cost_usd < 0.001:
        return f"${cost_usd:.6f}"
    if cost_usd < 1.0:
        return f"${cost_usd:.4f}"
    return f"${cost_usd:.2f}"
