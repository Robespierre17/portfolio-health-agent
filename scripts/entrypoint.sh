#!/bin/bash
# Production entrypoint — pulls versioned model artifact from GCS then starts uvicorn.
#
# Required env vars:
#   GCS_BUCKET      — e.g. my-project-models
#   MODEL_VERSION   — e.g. v1.0.0  (maps to gs://$GCS_BUCKET/models/$MODEL_VERSION/)
#
# Optional (defaults shown):
#   MODEL_PATH              — local destination (default: models/health_scorer.ubj)
#   FEATURE_BASELINE_PATH   — local destination (default: models/feature_baseline.parquet)
#   PORT                    — uvicorn port (default: 8080)

set -euo pipefail

MODEL_PATH="${MODEL_PATH:-models/health_scorer.ubj}"
FEATURE_BASELINE_PATH="${FEATURE_BASELINE_PATH:-models/feature_baseline.parquet}"
PORT="${PORT:-8080}"

if [[ -z "${GCS_BUCKET:-}" ]]; then
  echo "[entrypoint] GCS_BUCKET not set — skipping model pull, using local artifact." >&2
else
  if [[ -z "${MODEL_VERSION:-}" ]]; then
    echo "[entrypoint] ERROR: GCS_BUCKET is set but MODEL_VERSION is not." >&2
    exit 1
  fi

  GCS_BASE="gs://${GCS_BUCKET}/models/${MODEL_VERSION}"
  echo "[entrypoint] Pulling model ${MODEL_VERSION} from ${GCS_BASE} …"

  mkdir -p "$(dirname "$MODEL_PATH")" "$(dirname "$FEATURE_BASELINE_PATH")"

  gcloud storage cp "${GCS_BASE}/health_scorer.ubj"          "$MODEL_PATH"
  gcloud storage cp "${GCS_BASE}/feature_baseline.parquet"   "$FEATURE_BASELINE_PATH"

  echo "[entrypoint] Model pull complete."
fi

echo "[entrypoint] Running Alembic migrations …"
alembic upgrade head

echo "[entrypoint] Starting uvicorn on port ${PORT} …"
exec uvicorn src.api.main:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 2 \
  --log-level "${LOG_LEVEL:-info}"
