"""Unit tests for agent tool handlers — no network, no DB, no API key."""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

from src.agent.tools import explain_feature, _generate_suggestions, _apply_suggestions, dispatch


# ── explain_feature ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_explain_feature_sharpe_poor():
    result = await explain_feature("sharpe", 0.2)
    assert result["feature"] == "sharpe"
    assert "poor" in result["assessment"]


@pytest.mark.asyncio
async def test_explain_feature_sharpe_strong():
    result = await explain_feature("sharpe", 1.8)
    assert "strong" in result["assessment"]


@pytest.mark.asyncio
async def test_explain_feature_drawdown_severe():
    result = await explain_feature("max_drawdown", -0.45)
    assert "severe" in result["assessment"]


@pytest.mark.asyncio
async def test_explain_feature_drawdown_shallow():
    result = await explain_feature("max_drawdown", -0.05)
    assert "shallow" in result["assessment"]


@pytest.mark.asyncio
async def test_explain_feature_unknown():
    result = await explain_feature("unknown_metric", 0.5)
    assert "error" in result


@pytest.mark.asyncio
async def test_explain_feature_all_names():
    features = ["volatility", "max_drawdown", "sharpe", "concentration_hhi", "avg_correlation"]
    values   = [0.20,          -0.15,          0.8,      0.15,                 0.45]
    for name, val in zip(features, values):
        result = await explain_feature(name, val)
        assert "error" not in result
        assert result["feature"] == name


# ── _generate_suggestions ─────────────────────────────────────────────────────

def test_suggestions_reduce_concentration():
    weights = {"AAPL": 0.70, "MSFT": 0.20, "GOOG": 0.10}
    features = {
        "concentration_hhi": 0.54,   # dominant driver
        "avg_correlation": 0.40,
        "volatility": 0.18,
        "max_drawdown": -0.12,
        "sharpe": 1.2,
    }
    suggestions = _generate_suggestions(weights, features)
    assert len(suggestions) > 0
    # AAPL should be trimmed (highest weight)
    aapl = next((s for s in suggestions if s["ticker"] == "AAPL"), None)
    assert aapl is not None
    assert aapl["suggested_weight"] < aapl["current_weight"]


def test_apply_suggestions_weights_sum_to_one():
    weights = {"AAPL": 0.50, "MSFT": 0.30, "GOOG": 0.20}
    suggestions = [
        {"ticker": "AAPL", "suggested_weight": 0.30},
        {"ticker": "MSFT", "suggested_weight": 0.30},
    ]
    new_weights = _apply_suggestions(weights, suggestions)
    assert abs(sum(new_weights.values()) - 1.0) < 1e-6


# ── dispatch ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_unknown_tool():
    result = await dispatch("nonexistent_tool", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_explain_feature_no_db():
    result = await dispatch("explain_feature", {"feature_name": "sharpe", "feature_value": 1.5})
    assert "error" not in result
    assert result["feature"] == "sharpe"


@pytest.mark.asyncio
async def test_dispatch_query_holdings_no_db():
    # Without a DB session the handler returns an error dict, not an exception
    result = await dispatch("query_holdings", {"portfolio_id": 1}, db=None)
    assert "error" in result
