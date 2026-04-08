"""CRUD for portfolios and holdings — Milestone 1 skeleton."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db

router = APIRouter()


class HoldingIn(BaseModel):
    ticker: str
    weight: float


class PortfolioIn(BaseModel):
    name: str
    owner: str
    holdings: list[HoldingIn]


@router.post("/", status_code=201)
async def create_portfolio(payload: PortfolioIn, db: AsyncSession = Depends(get_db)):
    # TODO M1: persist to DB
    return {"message": "created", "payload": payload}


@router.get("/{portfolio_id}/holdings")
async def get_holdings(portfolio_id: int, db: AsyncSession = Depends(get_db)):
    # TODO M1: fetch from DB
    return {"portfolio_id": portfolio_id, "holdings": []}
