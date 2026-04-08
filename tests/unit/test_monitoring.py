"""Unit tests for PSI monitoring."""
import numpy as np
import pytest

from src.monitoring.metrics import psi, compute_all_psi
import pandas as pd


def test_psi_identical_distributions():
    x = np.random.default_rng(0).normal(0, 1, 1000)
    assert psi(x, x) == pytest.approx(0.0, abs=1e-6)


def test_psi_very_different_distributions():
    rng = np.random.default_rng(1)
    expected = rng.normal(0, 1, 1000)
    actual = rng.normal(5, 1, 1000)  # completely shifted
    assert psi(expected, actual) > 0.2


def test_compute_all_psi_returns_dict():
    rng = np.random.default_rng(2)
    baseline = pd.DataFrame({"vol": rng.normal(0.2, 0.05, 500), "sharpe": rng.normal(1.0, 0.3, 500)})
    current = pd.DataFrame({"vol": rng.normal(0.2, 0.05, 100), "sharpe": rng.normal(1.0, 0.3, 100)})
    result = compute_all_psi(baseline, current)
    assert set(result.keys()) == {"vol", "sharpe"}
