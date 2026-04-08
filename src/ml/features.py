"""
Milestone 1 — feature engineering.

Given a portfolio (dict of ticker→weight) and a DataFrame of daily prices,
compute the 5 risk features fed into the XGBoost scorer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


TRADING_DAYS = 252
FEATURE_COLS = ["volatility", "max_drawdown", "sharpe", "concentration_hhi", "avg_correlation"]


def portfolio_returns(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted daily portfolio returns from a price DataFrame (columns = tickers)."""
    tickers = [t for t in weights if t in prices.columns]
    w = np.array([weights[t] for t in tickers])
    w = w / w.sum()  # re-normalise in case of missing tickers
    ret = prices[tickers].pct_change().dropna()
    return ret @ w


def annualised_volatility(returns: pd.Series) -> float:
    """Annualised standard deviation of daily returns."""
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def max_drawdown(returns: pd.Series) -> float:
    """Maximum peak-to-trough drawdown (negative float)."""
    cum = (1 + returns).cumprod()
    rolling_max = cum.cummax()
    drawdown = (cum - rolling_max) / rolling_max
    return float(drawdown.min())


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.05) -> float:
    """Annualised Sharpe ratio (daily risk-free rate assumed constant)."""
    excess = returns - risk_free / TRADING_DAYS
    if returns.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(TRADING_DAYS))


def concentration_hhi(weights: dict[str, float]) -> float:
    """Herfindahl-Hirschman Index — 1/n (perfectly diversified) → 1 (single asset)."""
    w = np.array(list(weights.values()))
    w = w / w.sum()
    return float((w**2).sum())


def avg_pairwise_correlation(prices: pd.DataFrame, weights: dict[str, float]) -> float:
    """Weighted-average pairwise Pearson correlation of holdings' daily returns."""
    tickers = [t for t in weights if t in prices.columns]
    if len(tickers) < 2:
        return 1.0
    ret = prices[tickers].pct_change().dropna()
    corr = ret.corr().values
    # upper-triangle without diagonal
    n = len(tickers)
    idx = np.triu_indices(n, k=1)
    return float(corr[idx].mean())


def compute_features(prices: pd.DataFrame, weights: dict[str, float]) -> dict[str, float]:
    """Return all 5 features as a plain dict."""
    port_ret = portfolio_returns(prices, weights)
    return {
        "volatility": annualised_volatility(port_ret),
        "max_drawdown": max_drawdown(port_ret),
        "sharpe": sharpe_ratio(port_ret),
        "concentration_hhi": concentration_hhi(weights),
        "avg_correlation": avg_pairwise_correlation(prices, weights),
    }
