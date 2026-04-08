"""Agent chat endpoint — Milestone 2."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.agent import run_agent
from src.db.session import get_db

router = APIRouter()


class AgentRequest(BaseModel):
    portfolio_id: int
    question: str


class AgentResponse(BaseModel):
    answer: str
    tool_calls: list[dict]
    usage: dict


@router.post("/chat", response_model=AgentResponse)
async def chat(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    # Embed portfolio_id into the question so the agent always has it in context
    scoped_question = f"[Portfolio ID: {req.portfolio_id}] {req.question}"
    result = await run_agent(scoped_question, db=db)
    return AgentResponse(**result)
