"""Smoke test for training pipeline — fast, no I/O."""
import numpy as np
import pytest

from src.ml.train import build_training_data, train


def test_synthetic_data_shape():
    df = build_training_data(n_samples=200)
    assert len(df) == 200
    assert "health_score" in df.columns
    assert df["health_score"].between(0, 100).all()


def test_train_returns_metrics():
    df = build_training_data(n_samples=500)
    _, metrics = train(df)
    assert "mae" in metrics
    assert metrics["mae"] < 15   # loose bound for smoke test
    assert metrics["r2"] > 0.5
