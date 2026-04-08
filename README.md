# Portfolio Health Score Agent

An XGBoost model that scores portfolios **0–100** from time-series risk features,
wrapped by an LLM agent (Claude) that can answer questions, explain risk drivers,
and suggest rebalancing actions.

---

## Architecture

```
                ┌──────────────────────────────────────────────────┐
                │                  FastAPI (Cloud Run)              │
                │                                                  │
  User ──────►  │  /agent/chat  ──►  LLM Agent (Claude)           │
                │                        │                         │
                │               ┌────────┼──────────────┐          │
                │               ▼        ▼              ▼          │
                │      get_health_score  query_holdings  suggest_rebalance
                │               │        │              │          │
                │               ▼        ▼              ▼          │
                │         XGBoost    Postgres        XGBoost       │
                │         Scorer     (holdings)      Scorer        │
                │               │                                  │
                │               ▼                                  │
                │         yfinance (price fetch)                   │
                └──────────────────────────────────────────────────┘
                         │                    │
                    Prometheus            Postgres
                    /metrics              (scores, prices)
```

### Risk features (XGBoost inputs)

| Feature | Description |
|---|---|
| `volatility` | Annualised std dev of portfolio daily returns |
| `max_drawdown` | Peak-to-trough drawdown over lookback window |
| `sharpe` | Annualised Sharpe ratio (rf = 5%) |
| `concentration_hhi` | Herfindahl-Hirschman Index of weights |
| `avg_correlation` | Mean pairwise Pearson correlation of holdings |

### LLM Agent tools

| Tool | Purpose |
|---|---|
| `get_health_score` | Score a portfolio 0–100 + return features |
| `query_holdings` | Fetch current ticker/weight breakdown from Postgres |
| `explain_feature` | NL explanation of a feature value vs benchmarks |
| `suggest_rebalance` | Weight adjustments to hit a target score |

---

## Milestone Plan

### M1 — Data + Model  ✅
- [x] DB schema (portfolios, holdings, prices) + Alembic migrations
- [x] yfinance price ingestion script (`scripts/ingest_prices.py`)
- [x] Feature engineering (`src/ml/features.py`)
- [x] XGBoost training on synthetic data (`src/ml/train.py`)
- [ ] `/scores/score` REST endpoint
- [ ] Unit tests for features, train, PSI

### M2 — Agent + Tools
- [ ] Anthropic tool-use agentic loop (`src/agent/agent.py`)
- [ ] Implement all 4 tool handlers
- [ ] `/agent/chat` endpoint wired up
- [ ] Integration tests with mocked Claude responses

### M3 — Eval Harness
- [ ] Golden Q&A set (`tests/eval/golden_qa.json`)
- [ ] LLM-as-judge faithfulness checker
- [ ] Tool-use correctness assertions
- [ ] ML backtest (walk-forward score calibration)
- [ ] CI step that gates on eval pass rate ≥ 90%

### M4 — Deploy + Monitor
- [ ] Docker + Cloud Run deployment (GitHub Actions CI/CD)
- [ ] Prometheus `/metrics` + Grafana dashboard
- [ ] PSI alerts for feature drift
- [ ] Score distribution shift detection
- [ ] Token cost tracking per request
- [ ] Alembic migration automation in deploy step

---

## Quick Start

```bash
# 1. Install deps
pip install -e ".[dev]"

# 2. Copy env
cp .env.example .env   # fill in your keys

# 3. Start Postgres
docker-compose up db -d

# 4. Train the model
python -m src.ml.train

# 5. Run tests
pytest tests/unit/ -q

# 6. Start API
uvicorn src.api.main:app --reload --port 8080
```

Or with full Docker Compose:
```bash
docker-compose up --build
```

---

## Project Structure

```
src/
  config.py              # Pydantic settings
  api/
    main.py              # FastAPI app
    routers/             # health, portfolios, scores, agent
  db/
    models.py            # SQLAlchemy ORM
    session.py           # Async session factory
  ml/
    features.py          # Risk feature computation
    train.py             # XGBoost training script
    predict.py           # Inference wrapper
  agent/
    tools.py             # Tool schemas + dispatch (M2)
    agent.py             # Agentic loop (M2)
  monitoring/
    metrics.py           # PSI, score drift helpers
tests/
  unit/                  # Fast, no-network tests
  integration/           # DB + API tests
  eval/
    golden_qa.json        # LLM eval golden set
models/                  # Trained model artefacts (.gitignored except .gitkeep)
data/                    # Raw price data (.gitignored except .gitkeep)
```
