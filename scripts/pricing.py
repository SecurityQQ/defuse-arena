#!/usr/bin/env python3
"""Model pricing and USD cost of a round.

The benchmark meters tokens because that is what the API reports, but a token is
not a unit of cost: the same round costs an order of magnitude more on Opus than
on Sol. Every economic quantity — spend, chips, efficiency — is therefore
denominated in USD, converted at grading time with the price table in
``web/pricing.json``.

Prices are ``[input, cached input, output]`` USD per 1M tokens.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRICING = ROOT / "web" / "pricing.json"

# effort suffixes the CLI appends to a family id
EFFORT = ("-none", "-low", "-medium", "-high", "-xhigh", "-max",
          "-low-fast", "-medium-fast", "-high-fast", "-xhigh-fast", "-max-fast")

_table = None
_normalized = None


def table():
    global _table, _normalized
    if _table is None:
        try:
            _table = json.load(open(PRICING)).get("models", {})
        except Exception:
            _table = {}
        # One family can be written with dots or dashes (gpt-6.1-sol vs
        # gpt-6-1-sol); the effort suffix is not part of the price.
        _normalized = {k.replace(".", "-"): v for k, v in _table.items()}
    return _table


def price(model_id):
    """[input, cached, output] per 1M tokens, or None when the model is unpriced."""
    t = table()
    if not model_id:
        return None
    names = [model_id]
    for suffix in EFFORT:
        if model_id.endswith(suffix):
            names.append(model_id[: -len(suffix)])
            break
    for name in names:
        if name in t:
            return t[name]
        alt = name.replace(".", "-")
        if alt in _normalized:
            return _normalized[alt]
    return None


def cost_usd(spend_row, model_id):
    """USD for one side of a round, from a spend.json row.

    ``billable`` in the harness is ``prompt - cached + completion``; the cost is
    the same split priced separately, because cached input is ~10x cheaper.
    Returns None when the model has no price.
    """
    p = price(model_id)
    if p is None:
        return None
    prompt = int(spend_row.get("prompt", 0) or 0)
    cached = int(spend_row.get("cached", 0) or 0)
    completion = int(spend_row.get("completion", 0) or 0)
    uncached = max(0, prompt - cached)
    return (uncached * p[0] + cached * p[1] + completion * p[2]) / 1_000_000.0
