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
# Selected explicitly via `docker compose up` (target: dev in docker-compose.yml).
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
# Non-root user, no dev deps. Final/default stage — used by Railway and plain
# `docker build .` with no --target flag. Must remain LAST so Docker's default
# build target resolves to prod.
# Model artifact is baked in at build time (see COPY models/ below).
# Set GCS_BUCKET to pull a versioned artifact from GCS instead (entrypoint.sh
# skips the pull when GCS_BUCKET is unset).
FROM python:3.9-slim AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

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

# Bake model artifact into the image so no external storage is needed at runtime.
# To upgrade the model: retrain, commit the new files, redeploy.
COPY models/ ./models/
RUN ls -la models/

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
