"""Investigator guard rails (10 §4): pricing, caps, off-by-default. No network, no API key needed."""
import types

import pytest

from app import config, investigator


def test_cost_math_per_model():
    # 40k input of which 24k cached + 5k output on GPT-6 Astra: 16k*$10 + 24k*$1 + 5k*$50 per 1M = $0.434
    assert investigator.CostMeter.cost_micros("gpt-6-astra", 40_000, 24_000, 5_000) == 434_000
    assert investigator.CostMeter.cost_micros("gpt-6.1-sol", 40_000, 24_000, 5_000) == 84_400
    assert investigator.CostMeter.cost_micros("gpt-6-luna", 40_000, 24_000, 5_000) == 4_340
    assert investigator.CostMeter.cost_micros("some-new-model", 1_000_000, 0, 0) == 10_000_000  # priced safe-side


def test_day_cap_refuses(world, monkeypatch):
    m = investigator.CostMeter(run_cap_usd="3", day_cap_usd="5")
    usage = types.SimpleNamespace(input_tokens=200_000, output_tokens=40_000,
                                  input_tokens_details=types.SimpleNamespace(cached_tokens=0))
    m.check()                                            # nothing spent yet
    m.add(usage, "gpt-6-astra", "test")                  # $2 + $2 = $4 spent today
    with pytest.raises(RuntimeError, match="day cap"):
        m.check()                                        # 4 + 3 (next run's cap) > 5


def test_off_by_default(monkeypatch):
    monkeypatch.setattr(config, "LLM_ENABLED", False)
    ok, why = investigator.ready()
    assert not ok and "LLM_ENABLED" in why
