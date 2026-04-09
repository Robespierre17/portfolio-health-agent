"""Load the trained model and score a portfolio."""
from __future__ import annotations

import functools

import numpy as np
import pandas as pd
import xgboost as xgb

from src.config import settings
from src.ml.features import FEATURE_COLS, compute_features


@functools.lru_cache(maxsize=1)
def _load_model() -> xgb.XGBRegressor:
    model = xgb.XGBRegressor()
    model.load_model(settings.model_path)
    return model


def score_portfolio(prices: pd.DataFrame, weights: dict[str, float]) -> dict:
    """
    Return health score (0–100) and all intermediate features.

    Args:
        prices: DataFrame with date index, ticker columns, adjusted-close values.
        weights: {ticker: weight} — need not sum exactly to 1 (normalised internally).

    Returns:
        {"score": float, "features": {feature_name: float}}
    """
    features = compute_features(prices, weights)
    row = pd.DataFrame([features])[FEATURE_COLS]
    model = _load_model()
    raw = float(model.predict(row)[0])
    score = float(np.clip(raw, 0, 100))
    return {"score": round(score, 2), "features": features}
