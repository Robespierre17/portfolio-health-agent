"""
Milestone 1 — XGBoost model training.

Usage:
    python -m src.ml.train [--output models/health_scorer.ubj]

Synthetic training data is generated here for bootstrapping.  In production
you would replace `build_training_data()` with real labelled portfolios.

Health score label (0–100) is constructed from a weighted combination of
normalised risk metrics — this is the "ground truth" proxy used before you
have human-labelled data.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.calibration import calibration_curve

from src.ml.features import FEATURE_COLS  # single source of truth

logger = logging.getLogger(__name__)

LABEL_COL = "health_score"


def build_training_data(n_samples: int = 5_000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic labelled portfolios.

    Feature ranges are calibrated to realistic equity portfolio values:
      - volatility: 0.05–0.60 annualised
      - max_drawdown: -0.80–0.0
      - sharpe: -2.0–3.0
      - concentration_hhi: 0.05 (equal-weight 20 stocks) – 1.0 (single stock)
      - avg_correlation: 0.0–0.95

    Label construction note
    -----------------------
    The health score is a fixed-weight sum of per-feature utility scores.
    Each utility is computed via _norm_clamp, which clips to known domain
    bounds rather than fitting on the sample — so test labels never see
    training statistics (no preprocessing leakage).

    The label is intentionally a smooth deterministic function of the features.
    That makes R² high by construction (the model learns the formula), not
    because of leakage. The value of the model over a hard-coded formula is
    that it generalises to real, noisy feature values from actual price data.
    """
    rng = np.random.default_rng(seed)

    vol = rng.uniform(0.05, 0.60, n_samples)
    dd = -rng.uniform(0.0, 0.80, n_samples)
    sharpe = rng.uniform(-2.0, 3.0, n_samples)
    hhi = rng.uniform(0.05, 1.0, n_samples)
    corr = rng.uniform(0.0, 0.95, n_samples)

    # Use fixed domain bounds (not sample min/max) so label computation is
    # identical at inference time and does not depend on batch statistics.
    score = (
        20 * _norm_clamp(sharpe,  lo=-2.0, hi=3.0)          # higher sharpe → better
        + 20 * (1 - _norm_clamp(vol,   lo=0.05, hi=0.60))   # lower vol → better
        + 20 * (1 - _norm_clamp(-dd,   lo=0.0,  hi=0.80))   # shallower drawdown → better
        + 20 * (1 - _norm_clamp(hhi,   lo=0.05, hi=1.0))    # lower concentration → better
        + 20 * (1 - _norm_clamp(corr,  lo=0.0,  hi=0.95))   # lower correlation → better
    )
    score = np.clip(score, 0, 100)

    df = pd.DataFrame(
        {
            "volatility": vol,
            "max_drawdown": dd,
            "sharpe": sharpe,
            "concentration_hhi": hhi,
            "avg_correlation": corr,
            LABEL_COL: score,
        }
    )
    return df


def _norm_clamp(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Scale x to [0, 1] using fixed domain bounds, then clamp."""
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def train(df: pd.DataFrame, time_ordered: bool = False) -> tuple[xgb.XGBRegressor, dict]:
    """
    Train XGBoost on df.

    Args:
        time_ordered: if True, the last 20% of rows (by position) become the
                      test set — appropriate when df is sorted by observation
                      date (real portfolio snapshots).  For i.i.d. synthetic
                      data pass False to use random shuffling.
    """
    X = df[FEATURE_COLS]
    y = df[LABEL_COL]

    if time_ordered:
        split = int(len(df) * 0.8)
        X_train, X_test = X.iloc[:split], X.iloc[split:]
        y_train, y_test = y.iloc[:split], y.iloc[split:]
    else:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        objective="reg:squarederror",
        eval_metric="mae",
        early_stopping_rounds=30,
        random_state=42,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    preds = model.predict(X_test)
    metrics = {
        "mae": float(mean_absolute_error(y_test, preds)),
        "r2": float(r2_score(y_test, preds)),
        "n_train": len(X_train),
        "n_test": len(X_test),
    }
    return model, metrics


def save_baseline(df: pd.DataFrame, path: Path) -> None:
    """Save feature distribution baseline for PSI monitoring."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df[FEATURE_COLS].to_parquet(path, index=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="models/health_scorer.ubj")
    parser.add_argument("--baseline", default="models/feature_baseline.parquet")
    parser.add_argument("--n-samples", type=int, default=5_000)
    args = parser.parse_args()

    logger.info("Building synthetic training data (%d samples)…", args.n_samples)
    df = build_training_data(n_samples=args.n_samples)

    logger.info("Training XGBoost model…")
    model, metrics = train(df)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(out_path))
    logger.info("Model saved → %s", out_path)

    metrics_path = out_path.with_suffix(".metrics.json")
    metrics_path.write_text(json.dumps(metrics, indent=2))
    logger.info("Metrics: %s", metrics)

    save_baseline(df, Path(args.baseline))
    logger.info("Feature baseline saved → %s", args.baseline)


if __name__ == "__main__":
    main()
