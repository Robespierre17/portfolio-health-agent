"""
Monitoring helpers — Milestone 4.

- PSI (Population Stability Index) for feature drift detection.
- Score distribution tracking.
- Token cost accumulation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """
    Population Stability Index between a baseline and current distribution.

    PSI < 0.1  → no significant change
    0.1–0.2    → moderate change, monitor
    > 0.2      → significant change, retrain

    Args:
        expected: baseline feature values (training distribution).
        actual:   current production feature values.
        buckets:  number of equal-width bins.

    Returns:
        PSI scalar.
    """
    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    breakpoints = np.linspace(min_val, max_val, buckets + 1)

    expected_pct = np.histogram(expected, bins=breakpoints)[0] / len(expected)
    actual_pct = np.histogram(actual, bins=breakpoints)[0] / len(actual)

    # Avoid division by zero
    expected_pct = np.where(expected_pct == 0, 1e-6, expected_pct)
    actual_pct = np.where(actual_pct == 0, 1e-6, actual_pct)

    return float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))


def compute_all_psi(baseline_df: pd.DataFrame, current_df: pd.DataFrame) -> dict[str, float]:
    """Return PSI for every feature column present in both DataFrames."""
    cols = [c for c in baseline_df.columns if c in current_df.columns]
    return {col: psi(baseline_df[col].values, current_df[col].values) for col in cols}
