"""
Price ingestion script — Milestone 1.

Fetches adjusted-close prices from yfinance for every ticker that appears in
the holdings table, then upserts them into the prices table.

Usage:
    # All tickers in the DB
    python -m scripts.ingest_prices

    # Specific tickers / lookback
    python -m scripts.ingest_prices --tickers AAPL MSFT GOOG --days 365
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.config import settings
from src.db.models import Holding, Price
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def fetch_tickers_from_db() -> list[str]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Holding.ticker).distinct())
        return [row[0] for row in result.all()]


async def upsert_prices(records: list[dict]) -> int:
    """Insert prices, skipping rows that already exist (upsert on ticker+date)."""
    if not records:
        return 0
    async with AsyncSessionLocal() as db:
        stmt = pg_insert(Price).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["ticker", "price_date"])
        await db.execute(stmt)
        await db.commit()
    return len(records)


def download_prices(tickers: list[str], days: int) -> pd.DataFrame:
    """Return a DataFrame indexed by date with one column per ticker."""
    end = date.today()
    start = end - timedelta(days=days)
    logger.info("Downloading prices for %d tickers (%s → %s)…", len(tickers), start, end)

    raw = yf.download(
        tickers,
        start=str(start),
        end=str(end),
        auto_adjust=True,
        progress=False,
    )["Close"]

    # yfinance returns a Series (not DataFrame) for a single ticker
    if isinstance(raw, pd.Series):
        raw = raw.to_frame(name=tickers[0])

    return raw.dropna(how="all")


async def run(tickers: list[str], days: int) -> None:
    prices_df = download_prices(tickers, days)

    records = []
    for ticker in prices_df.columns:
        series = prices_df[ticker].dropna()
        for dt, close in series.items():
            records.append(
                {
                    "ticker": ticker,
                    "price_date": dt.date() if hasattr(dt, "date") else dt,
                    "close": float(close),
                }
            )

    inserted = await upsert_prices(records)
    logger.info("Upserted %d price rows for %d tickers.", inserted, len(prices_df.columns))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="*", help="Tickers to fetch (default: all in DB)")
    parser.add_argument("--days", type=int, default=settings.price_lookback_days)
    args = parser.parse_args()

    async def _run():
        tickers = args.tickers or await fetch_tickers_from_db()
        if not tickers:
            logger.warning("No tickers found. Add holdings to the DB first.")
            return
        await run(tickers, args.days)

    asyncio.run(_run())


if __name__ == "__main__":
    main()
