"""Score endpoint — Milestone 1."""
from __future__ import annotations

import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.ml.predict import score_portfolio

router = APIRouter()


class ScoreRequest(BaseModel):
    weights: dict[str, float]   # {"AAPL": 0.4, "MSFT": 0.3, "GOOG": 0.3}
    lookback_days: int = 365


@router.post("/score")
async def score(req: ScoreRequest):
    tickers = list(req.weights.keys())
    prices = yf.download(
        tickers,
        period=f"{req.lookback_days}d",
        auto_adjust=True,
        progress=False,
    )["Close"]

    if prices.empty:
        raise HTTPException(status_code=422, detail="Could not fetch prices for given tickers")

    result = score_portfolio(prices, req.weights)
    return result
