FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ── deps layer (cached unless pyproject.toml changes) ────────────────────────
COPY pyproject.toml ./
RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# ── source layer ──────────────────────────────────────────────────────────────
COPY src/ ./src/
COPY models/ ./models/
COPY alembic.ini ./

EXPOSE 8080

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
