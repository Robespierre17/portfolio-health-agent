"""
PSI drift detection job — Milestone 4.

Compares the feature distribution of recent production health-score records
against the training baseline, writes results to drift_runs, and exits non-zero
if any feature exceeds the configured PSI alert threshold.

Usage:
    python -m scripts.check_drift                  # default 30-day window
    python -m scripts.check_drift --window-days 7  # shorter window

Exit codes:
    0 — no alerts (or insufficient data to evaluate)
    1 — one or more features exceeded psi_threshold
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from src.config import settings
from src.db.models import DriftRun, HealthScore
from src.db.session import AsyncSessionLocal
from src.ml.features import FEATURE_COLS
from src.monitoring.metrics import compute_all_psi
from src.monitoring.prometheus import feature_psi

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Minimum current observations required before running PSI.
# Below this the distribution estimate is too noisy to be actionable.
MIN_OBSERVATIONS = 30


def load_baseline(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Feature baseline not found at {path}. "
            "Run `python -m src.ml.train` to generate it."
        )
    return pd.read_parquet(path)


async def fetch_current(window_days: int) -> pd.DataFrame:
    cutoff = datetime.utcnow() - timedelta(days=window_days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(HealthScore).where(HealthScore.scored_at >= cutoff)
        )
        rows = result.scalars().all()

    if not rows:
        return pd.DataFrame(columns=FEATURE_COLS)

    records = [
        {feat: getattr(row, feat) for feat in FEATURE_COLS}
        for row in rows
    ]
    return pd.DataFrame(records).dropna()


async def write_results(
    run_at: datetime,
    psi_values: dict[str, float],
    baseline_n: int,
    current_n: int,
    window_days: int,
) -> None:
    async with AsyncSessionLocal() as db:
        for feat, psi_val in psi_values.items():
            alert = psi_val > settings.psi_threshold
            db.add(DriftRun(
                run_at=run_at,
                feature=feat,
                psi=round(psi_val, 6),
                baseline_n=baseline_n,
                current_n=current_n,
                alert=alert,
                window_days=window_days,
            ))
        await db.commit()


async def run(window_days: int) -> int:
    logger.info(
        "PSI drift check | window=%d days | threshold=%.2f",
        window_days, settings.psi_threshold,
    )

    # ── Load baseline ─────────────────────────────────────────────────────
    baseline_path = Path(settings.feature_baseline_path)
    try:
        baseline_df = load_baseline(baseline_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 0  # not an alert condition — model may not be trained yet

    baseline_df = baseline_df[FEATURE_COLS].dropna()
    logger.info("Baseline: %d rows from %s", len(baseline_df), baseline_path)

    # ── Fetch recent production observations ──────────────────────────────
    current_df = await fetch_current(window_days)
    logger.info("Current window (%d days): %d rows", window_days, len(current_df))

    if len(current_df) < MIN_OBSERVATIONS:
        logger.info(
            "Fewer than %d observations in window — skipping PSI (not an alert).",
            MIN_OBSERVATIONS,
        )
        return 0

    # ── Compute PSI per feature ───────────────────────────────────────────
    psi_values = compute_all_psi(baseline_df, current_df)

    run_at = datetime.utcnow()
    any_alert = False

    logger.info("─" * 50)
    for feat, psi_val in sorted(psi_values.items()):
        alert = psi_val > settings.psi_threshold
        if alert:
            any_alert = True
        feature_psi.labels(feature=feat).set(psi_val)
        level = logging.WARNING if alert else logging.INFO
        status = "⚠  ALERT" if alert else "   OK   "
        logger.log(level, "  %s  %-22s  PSI = %.4f", status, feat, psi_val)

    logger.info("─" * 50)
    logger.info(
        "PSI reference: <0.10 stable | 0.10–0.20 monitor | >0.20 retrain"
    )

    # ── Persist results ───────────────────────────────────────────────────
    await write_results(
        run_at=run_at,
        psi_values=psi_values,
        baseline_n=len(baseline_df),
        current_n=len(current_df),
        window_days=window_days,
    )
    logger.info("Results written to drift_runs table (run_at=%s).", run_at.isoformat())

    if any_alert:
        logger.warning(
            "One or more features exceeded PSI threshold %.2f — consider retraining.",
            settings.psi_threshold,
        )
        return 1

    logger.info("All features within threshold — no action required.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="PSI feature drift detection job.")
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="Number of days of recent health_scores to use as the current distribution (default: 30)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.window_days)))


if __name__ == "__main__":
    main()
