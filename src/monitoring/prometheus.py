"""
Custom Prometheus metrics for the portfolio health agent.

HTTP-level metrics (request count, latency by endpoint, status codes) are
handled automatically by prometheus_fastapi_instrumentator in api/main.py.
This module defines the business-level metrics that need explicit recording.

Usage:
    from src.monitoring.prometheus import health_score_histogram
    health_score_histogram.observe(score)
"""
from prometheus_client import Counter, Gauge, Histogram

# ── Scoring ───────────────────────────────────────────────────────────────────

health_score_histogram = Histogram(
    "health_score_value",
    "Distribution of portfolio health scores (0–100)",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
)

# ── Agent ─────────────────────────────────────────────────────────────────────

agent_tokens_total = Counter(
    "agent_tokens_total",
    "Anthropic API tokens consumed by the agent loop",
    ["direction"],  # "input" | "output"
)

agent_tool_calls_total = Counter(
    "agent_tool_calls_total",
    "Tool invocations dispatched by the agent, by tool name",
    ["tool"],
)

agent_latency_seconds = Histogram(
    "agent_latency_seconds",
    "End-to-end agent request latency (question received → answer returned)",
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
)

# ── Drift (updated by the PSI drift job — Step 7) ────────────────────────────

feature_psi = Gauge(
    "feature_psi",
    "Population Stability Index per feature vs training baseline",
    ["feature"],
)
