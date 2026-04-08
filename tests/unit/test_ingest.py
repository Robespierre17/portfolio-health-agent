"""Unit tests for price ingestion helpers (no network, no DB)."""
from __future__ import annotations

import pandas as pd

from scripts.ingest_prices import download_prices


def test_download_prices_returns_dataframe(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=5)
    mock_close = pd.DataFrame(
        {"AAPL": [150.0, 151.0, 152.0, 153.0, 154.0],
         "MSFT": [300.0, 301.0, 302.0, 303.0, 304.0]},
        index=dates,
    )
    # yf.download returns a DataFrame; script accesses ["Close"] on it
    monkeypatch.setattr(
        "scripts.ingest_prices.yf.download",
        lambda *a, **kw: {"Close": mock_close},
    )

    result = download_prices(["AAPL", "MSFT"], days=5)
    assert isinstance(result, pd.DataFrame)
    assert set(result.columns) == {"AAPL", "MSFT"}
    assert len(result) == 5


def test_download_prices_single_ticker_returns_dataframe(monkeypatch):
    """Single-ticker yfinance returns a Series under 'Close' — ensure we promote to DataFrame."""
    dates = pd.date_range("2024-01-01", periods=5)
    mock_series = pd.Series([150.0, 151.0, 152.0, 153.0, 154.0], index=dates)

    monkeypatch.setattr(
        "scripts.ingest_prices.yf.download",
        lambda *a, **kw: {"Close": mock_series},
    )

    result = download_prices(["AAPL"], days=5)
    assert isinstance(result, pd.DataFrame)
    assert "AAPL" in result.columns
    assert len(result) == 5
