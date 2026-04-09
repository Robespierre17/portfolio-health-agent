# Portfolio Health Score Agent

An XGBoost model that scores portfolios **0–100** from time-series risk features,
wrapped by an LLM agent (Claude) that can answer questions, explain risk drivers,
and suggest rebalancing actions.

---

## Architecture

```
                ┌──────────────────────────────────────────────────┐
                │                  FastAPI (Railway)                │
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
- [x] Multi-stage Dockerfile (builder → prod → dev)
- [x] Two-tier eval in CI (smoke on PR, full on merge)
- [x] Railway deployment — full eval gates every merge to main
- [ ] Prometheus `/metrics` + Grafana dashboard
- [ ] PSI alerts for feature drift
- [ ] Score distribution shift detection
- [ ] Token cost tracking per request

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

## Deploying to Railway

### First-time setup (Railway dashboard)

1. New project → **Deploy from GitHub repo** → select this repo
2. Service settings → **Build** — Dockerfile is auto-detected; no target needed (prod is the default stage)
3. Service settings → **Deploy** — disable "Deploy on push" (CI controls deploys)
4. Add a **PostgreSQL** database service to the project
5. Set these environment variables on the API service:

| Variable | Value |
|----------|-------|
| `APP_ENV` | `production` |
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` |
| `DATABASE_URL` | Copy Railway's injected Postgres URL, change `postgresql://` → `postgresql+asyncpg://` |
| `MODEL_VERSION` | `v1.0.0` |

### CI/CD

Merges to `main` run the full eval (31 cases, ≥85% pass rate + 100% tool correctness). If the gate passes, the workflow deploys automatically via the Railway CLI.

Add these secrets in repo **Settings → Secrets and variables → Actions**:

| Secret | Where to find it |
|--------|-----------------|
| `RAILWAY_TOKEN` | Railway dashboard → Account settings → Tokens |
| `RAILWAY_PROJECT_ID` | Railway project → Settings → General → Project ID |
| `RAILWAY_SERVICE_ID` | Railway API service → Settings → Service ID |
| `ANTHROPIC_API_KEY` | Used by the eval job in CI |

### Updating the model

Retrain locally, commit the new `models/` artifacts, open a PR. The smoke eval gates the PR; the full eval + Railway deploy run on merge.

> **Future:** move artifacts to S3/GCS with `MODEL_VERSION` pinning so model and code deploy independently. See `NOTES.md`.

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
