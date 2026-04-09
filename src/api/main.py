"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.routers import agent, health, portfolios, scores
from src.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Portfolio Health Agent",
    description="XGBoost health scorer + LLM agent for portfolio risk analysis",
    version="0.1.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# localhost:3000 for local Next.js dev; FRONTEND_URL for the Vercel deployment.
_origins = ["http://localhost:3000"]
if settings.frontend_url:
    _origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── Prometheus metrics at /metrics ───────────────────────────────────────────
Instrumentator().instrument(app).expose(app)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(portfolios.router, prefix="/portfolios", tags=["portfolios"])
app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(agent.router, prefix="/agent", tags=["agent"])
