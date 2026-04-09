# ── Stage 1: build wheel ──────────────────────────────────────────────────────
# Installs deps and builds a wheel so the prod stage has no build tooling.
FROM python:3.9-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN pip install --upgrade pip build

COPY pyproject.toml ./
COPY src/ ./src/

# Build app wheel + download all production dependency wheels into /wheels.
# --no-deps would only build the app wheel; without it pip also fetches all deps.
RUN pip wheel --wheel-dir /wheels .


# ── Stage 2: dev ──────────────────────────────────────────────────────────────
# Editable install, all dev deps, runs as root — for local docker-compose only.
FROM python:3.9-slim AS dev

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY src/ ./src/
COPY alembic.ini ./
# models/ mounted as a volume in docker-compose so the local artifact is used

EXPOSE 8080
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]


# ── Stage 3: prod ─────────────────────────────────────────────────────────────
# Non-root user, no dev deps, model pulled from GCS at startup.
FROM python:3.9-slim AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# gcloud CLI for GCS model pull
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
       https://packages.cloud.google.com/apt cloud-sdk main" \
       > /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
       | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
    && apt-get update && apt-get install -y --no-install-recommends \
        google-cloud-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR /app

# Install only production wheels
COPY --from=builder /wheels /wheels
RUN pip install --upgrade pip && pip install --no-index --find-links /wheels portfolio-health-agent \
    && rm -rf /wheels

COPY alembic.ini ./
COPY scripts/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

# models/ dir must exist so entrypoint can write into it
RUN mkdir -p models && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
