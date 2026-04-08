"""Unit tests for feature engineering (no DB, no network)."""
import numpy as np
import pandas as pd
import pytest

from src.ml.features import (
    annualised_volatility,
    avg_pairwise_correlation,
    concentration_hhi,
    compute_features,
    max_drawdown,
    portfolio_returns,
    sharpe_ratio,
)


@pytest.fixture
def synthetic_prices() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2023-01-01", periods=252)
    prices = pd.DataFrame(
        {
            "AAPL": 150 * np.cumprod(1 + rng.normal(0.0005, 0.015, 252)),
            "MSFT": 280 * np.cumprod(1 + rng.normal(0.0004, 0.012, 252)),
            "GOOG": 100 * np.cumprod(1 + rng.normal(0.0003, 0.018, 252)),
        },
        index=dates,
    )
    return prices


def test_volatility_positive(synthetic_prices):
    weights = {"AAPL": 0.4, "MSFT": 0.4, "GOOG": 0.2}
    ret = portfolio_returns(synthetic_prices, weights)
    vol = annualised_volatility(ret)
    assert 0 < vol < 1.0


def test_max_drawdown_negative(synthetic_prices):
    weights = {"AAPL": 0.4, "MSFT": 0.4, "GOOG": 0.2}
    ret = portfolio_returns(synthetic_prices, weights)
    dd = max_drawdown(ret)
    assert dd <= 0


def test_sharpe_range(synthetic_prices):
    weights = {"AAPL": 0.4, "MSFT": 0.4, "GOOG": 0.2}
    ret = portfolio_returns(synthetic_prices, weights)
    s = sharpe_ratio(ret)
    assert -5 < s < 10


def test_hhi_single_asset():
    assert concentration_hhi({"AAPL": 1.0}) == pytest.approx(1.0)


def test_hhi_equal_weight():
    n = 10
    weights = {f"T{i}": 1 / n for i in range(n)}
    assert concentration_hhi(weights) == pytest.approx(1 / n, abs=1e-6)


def test_correlation_two_identical_series():
    rng = np.random.default_rng(99)
    dates = pd.date_range("2023-01-01", periods=100)
    returns = rng.normal(0.001, 0.01, 100)
    # Both series have identical returns → perfect correlation
    px = pd.DataFrame(
        {"A": np.cumprod(1 + returns), "B": np.cumprod(1 + returns)},
        index=dates,
    )
    corr = avg_pairwise_correlation(px, {"A": 0.5, "B": 0.5})
    assert corr == pytest.approx(1.0, abs=1e-6)


def test_compute_features_keys(synthetic_prices):
    weights = {"AAPL": 0.4, "MSFT": 0.4, "GOOG": 0.2}
    features = compute_features(synthetic_prices, weights)
    assert set(features.keys()) == {"volatility", "max_drawdown", "sharpe", "concentration_hhi", "avg_correlation"}
