"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// ── Types ─────────────────────────────────────────────────────────────────────

type Row = { ticker: string; weight: string };

type ScoreResult = {
  score: number;
  features: Record<string, number>;
};

// ── Feature display config ────────────────────────────────────────────────────

const FEATURES: {
  key: string;
  label: string;
  format: (v: number) => string;
}[] = [
  {
    key: "volatility",
    label: "Volatility",
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "max_drawdown",
    label: "Max Drawdown",
    format: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "sharpe",
    label: "Sharpe Ratio",
    format: (v) => v.toFixed(2),
  },
  {
    key: "concentration_hhi",
    label: "Concentration (HHI)",
    format: (v) => v.toFixed(3),
  },
  {
    key: "avg_correlation",
    label: "Avg Correlation",
    format: (v) => v.toFixed(2),
  },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreColorClass(score: number) {
  if (score >= 70) return "text-green-700 bg-green-50 border-green-200";
  if (score >= 40) return "text-yellow-700 bg-yellow-50 border-yellow-200";
  return "text-red-700 bg-red-50 border-red-200";
}

function scoreLabel(score: number) {
  if (score >= 70) return "Well-diversified";
  if (score >= 40) return "Moderate risk";
  return "High risk";
}

// ── Initial rows match the seed portfolio so the demo works out of the box ───

const INITIAL_ROWS: Row[] = [
  { ticker: "AAPL", weight: "30" },
  { ticker: "MSFT", weight: "25" },
  { ticker: "GOOGL", weight: "20" },
  { ticker: "AMZN", weight: "15" },
  { ticker: "NVDA", weight: "10" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function PortfolioScorer() {
  const [rows, setRows] = useState<Row[]>(INITIAL_ROWS);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function addRow() {
    setRows((r) => [...r, { ticker: "", weight: "" }]);
  }

  function removeRow(i: number) {
    setRows((r) => r.filter((_, idx) => idx !== i));
  }

  function updateRow(i: number, field: keyof Row, value: string) {
    setRows((r) =>
      r.map((row, idx) => (idx === i ? { ...row, [field]: value } : row))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    // Validate rows
    for (const row of rows) {
      if (!row.ticker.trim()) {
        setError("Every row needs a ticker symbol.");
        return;
      }
      const w = parseFloat(row.weight);
      if (isNaN(w) || w <= 0) {
        setError("Every weight must be a positive number.");
        return;
      }
    }
    const total = rows.reduce((sum, r) => sum + parseFloat(r.weight), 0);
    if (Math.abs(total - 100) > 0.5) {
      setError(`Weights sum to ${total.toFixed(1)}% — must total 100%.`);
      return;
    }

    // Build request payload (weights as decimals)
    const weights: Record<string, number> = {};
    for (const row of rows) {
      weights[row.ticker.trim().toUpperCase()] = parseFloat(row.weight) / 100;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/scores/score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ weights, lookback_days: 365 }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as { detail?: string }).detail ?? `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <h2 className="text-lg font-medium text-gray-800 mb-5">
        Portfolio Scorer
      </h2>

      <form onSubmit={handleSubmit} className="space-y-2">
        {/* Column headers */}
        <div className="grid grid-cols-[1fr_110px_32px] gap-2 px-1 mb-1">
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            Ticker
          </span>
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wide">
            Weight %
          </span>
          <span />
        </div>

        {/* Rows */}
        {rows.map((row, i) => (
          <div
            key={i}
            className="grid grid-cols-[1fr_110px_32px] gap-2 items-center"
          >
            <input
              type="text"
              value={row.ticker}
              onChange={(e) => updateRow(i, "ticker", e.target.value)}
              placeholder="AAPL"
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-mono uppercase placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <input
              type="number"
              value={row.weight}
              onChange={(e) => updateRow(i, "weight", e.target.value)}
              placeholder="0"
              min="0.1"
              max="100"
              step="0.1"
              className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="button"
              onClick={() => removeRow(i)}
              disabled={rows.length === 1}
              className="flex items-center justify-center text-gray-300 hover:text-red-400 disabled:opacity-0 text-xl leading-none transition-colors"
              aria-label="Remove row"
            >
              ×
            </button>
          </div>
        ))}

        {/* Actions row */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="button"
            onClick={addRow}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
          >
            + Add ticker
          </button>
          <div className="flex-1" />
          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Scoring…" : "Score portfolio"}
          </button>
        </div>
      </form>

      {/* Validation error */}
      {error && (
        <p className="mt-3 text-sm text-red-600">{error}</p>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm animate-pulse space-y-3">
          <div className="flex gap-4">
            <div className="h-16 w-20 rounded-lg bg-gray-100" />
            <div className="space-y-2 flex-1 pt-1">
              <div className="h-3 bg-gray-100 rounded w-24" />
              <div className="h-3 bg-gray-100 rounded w-16" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 pt-1">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-100 rounded-md" />
            ))}
          </div>
        </div>
      )}

      {/* Result card */}
      {result && !loading && (
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          {/* Score badge + label */}
          <div className="flex items-center gap-4">
            <div
              className={`rounded-xl border px-5 py-3 text-center min-w-[80px] ${scoreColorClass(result.score)}`}
            >
              <div className="text-4xl font-bold tabular-nums leading-none">
                {result.score.toFixed(1)}
              </div>
              <div className="text-xs font-medium mt-1 opacity-70">/ 100</div>
            </div>
            <div>
              <div className="text-base font-semibold text-gray-800">
                Health Score
              </div>
              <div className="text-sm text-gray-500 mt-0.5">
                {scoreLabel(result.score)}
              </div>
            </div>
          </div>

          {/* Feature grid */}
          <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 gap-3">
            {FEATURES.map(({ key, label, format }) => {
              const val = result.features[key];
              return (
                <div key={key} className="rounded-lg bg-gray-50 px-3 py-2.5">
                  <div className="text-xs text-gray-400">{label}</div>
                  <div className="text-sm font-semibold text-gray-800 mt-0.5 tabular-nums">
                    {val != null ? format(val) : "—"}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
