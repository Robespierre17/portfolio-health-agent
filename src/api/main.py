"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.routers import health, portfolios, scores, agent

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Portfolio Health Agent",
    description="XGBoost health scorer + LLM agent for portfolio risk analysis",
    version="0.1.0",
)

# ── Prometheus metrics at /metrics ───────────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(portfolios.router, prefix="/portfolios", tags=["portfolios"])
app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])
