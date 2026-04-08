"""
Tool implementations for the LLM agent — Milestone 2.

Each handler corresponds to one Anthropic tool_use block.
All DB-touching handlers receive an AsyncSession injected by the agent loop.
"""
from __future__ import annotations

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Holding, Portfolio
from src.ml.predict import score_portfolio

# ── Tool schemas (passed to Anthropic API as tools=) ─────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "get_health_score",
        "description": (
            "Score a portfolio 0–100 using the XGBoost risk model. "
            "Returns the score plus the five underlying risk features: "
            "volatility, max_drawdown, sharpe, concentration_hhi, avg_correlation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "integer", "description": "DB portfolio ID"},
                "lookback_days": {
                    "type": "integer",
                    "description": "Number of calendar days of price history to use",
                    "default": 365,
                },
            },
            "required": ["portfolio_id"],
        },
    },
    {
        "name": "query_holdings",
        "description": "Fetch the current holdings (ticker + weight) for a portfolio from the database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "integer"},
            },
            "required": ["portfolio_id"],
        },
    },
    {
        "name": "explain_feature",
        "description": (
            "Return a plain-English explanation of what a specific risk feature means, "
            "how the given value compares to typical benchmarks, and whether it is a concern."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature_name": {
                    "type": "string",
                    "enum": [
                        "volatility",
                        "max_drawdown",
                        "sharpe",
                        "concentration_hhi",
                        "avg_correlation",
                    ],
                },
                "feature_value": {"type": "number"},
            },
            "required": ["feature_name", "feature_value"],
        },
    },
    {
        "name": "suggest_rebalance",
        "description": (
            "Analyse the portfolio's risk features and suggest concrete weight adjustments "
            "to improve the health score. Returns current score, projected score, and "
            "a list of suggested weight changes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "portfolio_id": {"type": "integer"},
                "target_score": {
                    "type": "number",
                    "description": "Desired health score 0–100 (default 75)",
                },
            },
            "required": ["portfolio_id"],
        },
    },
]

# ── Benchmark thresholds for explain_feature ─────────────────────────────────

_THRESHOLDS = {
    "volatility": [
        (0.15, "low — well-controlled risk"),
        (0.25, "moderate — typical for a diversified equity portfolio"),
        (float("inf"), "high — portfolio swings significantly; consider de-risking"),
    ],
    "max_drawdown": [
        (-0.10, "shallow — strong downside protection"),
        (-0.20, "moderate — expect occasional -10 to -20% troughs"),
        (float("inf"), "severe — portfolio has experienced large peak-to-trough losses"),
    ],
    "sharpe": [
        (0.5,  "poor — returns don't justify the risk taken"),
        (1.0,  "adequate — reasonable risk-adjusted return"),
        (float("inf"), "strong — good return per unit of risk"),
    ],
    "concentration_hhi": [
        (0.10, "diversified — no single holding dominates"),
        (0.25, "moderately concentrated — a few positions are oversized"),
        (float("inf"), "highly concentrated — idiosyncratic risk is significant"),
    ],
    "avg_correlation": [
        (0.30, "low — holdings move independently, good diversification benefit"),
        (0.60, "moderate — some co-movement; diversification partially effective"),
        (float("inf"), "high — holdings are highly correlated; diversification benefit is limited"),
    ],
}

_DESCRIPTIONS = {
    "volatility": "annualised standard deviation of daily portfolio returns",
    "max_drawdown": "largest peak-to-trough decline over the lookback period",
    "sharpe": "annualised excess return divided by volatility (risk-free rate = 5%)",
    "concentration_hhi": (
        "Herfindahl-Hirschman Index of portfolio weights — "
        "1/n for equal-weight, 1.0 for a single-stock portfolio"
    ),
    "avg_correlation": "mean pairwise Pearson correlation of holdings' daily returns",
}


# ── Handler implementations ───────────────────────────────────────────────────

async def get_health_score(
    portfolio_id: int,
    lookback_days: int = 365,
    db: AsyncSession | None = None,
) -> dict:
    weights = await _fetch_weights(portfolio_id, db)
    if not weights:
        return {"error": f"Portfolio {portfolio_id} not found or has no holdings."}

    tickers = list(weights.keys())
    prices = yf.download(
        tickers,
        period=f"{lookback_days}d",
        auto_adjust=True,
        progress=False,
    )["Close"]

    if hasattr(prices, "squeeze"):
        # single-ticker: yfinance returns a Series
        if len(tickers) == 1 and not hasattr(prices.columns, "__len__"):
            prices = prices.to_frame(name=tickers[0])

    if prices.empty:
        return {"error": "Could not fetch price data for the portfolio's holdings."}

    result = score_portfolio(prices, weights)
    result["portfolio_id"] = portfolio_id
    result["lookback_days"] = lookback_days
    return result


async def query_holdings(
    portfolio_id: int,
    db: AsyncSession | None = None,
) -> dict:
    weights = await _fetch_weights(portfolio_id, db)
    if not weights:
        return {"error": f"Portfolio {portfolio_id} not found or has no holdings."}
    return {
        "portfolio_id": portfolio_id,
        "holdings": [{"ticker": t, "weight": round(w, 6)} for t, w in weights.items()],
    }


async def explain_feature(feature_name: str, feature_value: float) -> dict:
    thresholds = _THRESHOLDS.get(feature_name)
    if not thresholds:
        return {"error": f"Unknown feature: {feature_name}"}

    # For max_drawdown the value is negative; compare abs for threshold lookup
    cmp_value = abs(feature_value) if feature_name == "max_drawdown" else feature_value

    label = thresholds[-1][1]
    for limit, desc in thresholds:
        if cmp_value <= abs(limit):
            label = desc
            break

    return {
        "feature": feature_name,
        "value": feature_value,
        "description": _DESCRIPTIONS[feature_name],
        "assessment": label,
    }


async def suggest_rebalance(
    portfolio_id: int,
    target_score: float = 75.0,
    db: AsyncSession | None = None,
) -> dict:
    weights = await _fetch_weights(portfolio_id, db)
    if not weights:
        return {"error": f"Portfolio {portfolio_id} not found or has no holdings."}

    tickers = list(weights.keys())
    prices = yf.download(
        tickers, period="365d", auto_adjust=True, progress=False
    )["Close"]

    if prices.empty:
        return {"error": "Could not fetch price data."}

    current = score_portfolio(prices, weights)
    current_score = current["score"]

    if current_score >= target_score:
        return {
            "portfolio_id": portfolio_id,
            "current_score": current_score,
            "target_score": target_score,
            "target_reachable": True,
            "best_achievable_score": current_score,
            "message": f"Portfolio already meets target score of {target_score}.",
            "suggestions": [],
        }

    # Identify the worst-scoring feature and suggest a targeted fix
    features = current["features"]
    suggestions = _generate_suggestions(weights, features)

    # Project score after applying suggestions
    projected_weights = _apply_suggestions(weights, suggestions)
    projected = score_portfolio(prices, projected_weights)
    projected_score = projected["score"]

    return {
        "portfolio_id": portfolio_id,
        "current_score": current_score,
        "projected_score": projected_score,
        "target_score": target_score,
        "target_reachable": projected_score >= target_score,
        "best_achievable_score": projected_score,
        "suggestions": suggestions,
        "projected_weights": projected_weights,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_weights(portfolio_id: int, db: AsyncSession | None) -> dict[str, float]:
    if db is None:
        return {}
    result = await db.execute(
        select(Holding.ticker, Holding.weight).where(Holding.portfolio_id == portfolio_id)
    )
    rows = result.all()
    return {row[0]: row[1] for row in rows}


def _generate_suggestions(
    weights: dict[str, float],
    features: dict[str, float],
) -> list[dict]:
    """
    Rule-based rebalancing suggestions derived from the worst feature.
    Returns a list of {ticker, current_weight, suggested_weight, reason}.
    """
    # Score each feature penalty (0 = no penalty, 1 = max penalty)
    penalties = {
        "concentration_hhi": features["concentration_hhi"],          # higher = worse
        "avg_correlation":   features["avg_correlation"],            # higher = worse
        "volatility":        min(features["volatility"] / 0.60, 1),  # normalise to 0–1
        "max_drawdown":      min(abs(features["max_drawdown"]) / 0.80, 1),
        "sharpe":            max(0, 1 - (features["sharpe"] + 2) / 5),  # lower sharpe = higher penalty
    }
    worst = max(penalties, key=penalties.__getitem__)

    sorted_tickers = sorted(weights, key=weights.__getitem__, reverse=True)
    n = len(sorted_tickers)
    equal_weight = round(1.0 / n, 6)

    if worst in ("concentration_hhi", "avg_correlation"):
        # Flatten the top-heavy positions toward equal weight
        suggestions = []
        for t in sorted_tickers:
            suggested = round((weights[t] + equal_weight) / 2, 6)
            if abs(suggested - weights[t]) > 0.005:
                suggestions.append({
                    "ticker": t,
                    "current_weight": round(weights[t], 6),
                    "suggested_weight": suggested,
                    "reason": f"Reduce {worst} by moving toward equal weight",
                })
        return suggestions

    if worst == "volatility":
        # Trim the two largest positions
        suggestions = []
        for t in sorted_tickers[:2]:
            suggested = round(weights[t] * 0.80, 6)
            suggestions.append({
                "ticker": t,
                "current_weight": round(weights[t], 6),
                "suggested_weight": suggested,
                "reason": "Trim oversized position to reduce portfolio volatility",
            })
        return suggestions

    # max_drawdown or sharpe → reduce all positions equally, implying cash buffer
    suggestions = []
    for t in sorted_tickers:
        suggested = round(weights[t] * 0.90, 6)
        suggestions.append({
            "ticker": t,
            "current_weight": round(weights[t], 6),
            "suggested_weight": suggested,
            "reason": f"Scale back exposure to improve {worst}",
        })
    return suggestions


def _apply_suggestions(
    weights: dict[str, float],
    suggestions: list[dict],
) -> dict[str, float]:
    """Return new weights dict with suggestions applied and re-normalised."""
    new_weights = dict(weights)
    for s in suggestions:
        new_weights[s["ticker"]] = s["suggested_weight"]
    total = sum(new_weights.values())
    return {t: w / total for t, w in new_weights.items()}


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def dispatch(name: str, tool_input: dict, db: AsyncSession | None = None) -> dict:
    if name == "get_health_score":
        return await get_health_score(db=db, **tool_input)
    if name == "query_holdings":
        return await query_holdings(db=db, **tool_input)
    if name == "explain_feature":
        return await explain_feature(**tool_input)
    if name == "suggest_rebalance":
        return await suggest_rebalance(db=db, **tool_input)
    return {"error": f"Unknown tool: {name}"}
