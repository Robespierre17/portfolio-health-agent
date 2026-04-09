"""
Seed a minimal portfolio for CI eval runs.

Creates portfolio id=1 with 5 holdings if they don't already exist.
Safe to run multiple times — all inserts use ON CONFLICT DO NOTHING.

Usage:
    python -m scripts.seed_ci_data
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.models import Holding, Portfolio
from src.db.session import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PORTFOLIO_ID   = 1
PORTFOLIO_NAME = "CI Test Portfolio"
PORTFOLIO_OWNER = "ci"

# Weights must sum to 1.0; tickers must have yfinance price data.
HOLDINGS: dict[str, float] = {
    "AAPL":  0.30,
    "MSFT":  0.25,
    "GOOGL": 0.20,
    "AMZN":  0.15,
    "NVDA":  0.10,
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # Portfolio row
        stmt = pg_insert(Portfolio).values(
            id=PORTFOLIO_ID,
            name=PORTFOLIO_NAME,
            owner=PORTFOLIO_OWNER,
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        await db.execute(stmt)
        logger.info("Portfolio %d upserted.", PORTFOLIO_ID)

        # Holdings rows
        for ticker, weight in HOLDINGS.items():
            stmt = pg_insert(Holding).values(
                portfolio_id=PORTFOLIO_ID,
                ticker=ticker,
                weight=weight,
            )
            stmt = stmt.on_conflict_do_nothing(constraint="uq_portfolio_ticker")
            await db.execute(stmt)
            logger.info("  Holding %s (%.0f%%) upserted.", ticker, weight * 100)

        await db.commit()
        logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
