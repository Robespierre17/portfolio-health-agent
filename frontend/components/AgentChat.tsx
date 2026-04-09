"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
const PORTFOLIO_ID = 1;

const EXAMPLE_PROMPTS = [
  "What's my biggest risk driver?",
  "How can I improve my health score?",
  "Explain my Sharpe ratio.",
];

// ── Types ─────────────────────────────────────────────────────────────────────

type ToolCall = {
  name: string;
  input: Record<string, unknown>;
  result: Record<string, unknown>;
};

type ChatResult = {
  answer: string;
  tool_calls: ToolCall[];
  usage: { input_tokens: number; output_tokens: number };
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function AgentChat() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ChatResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setError(null);
    setResult(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ portfolio_id: PORTFOLIO_ID, question: q }),
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
      <h2 className="text-lg font-medium text-gray-800 mb-1">Agent Chat</h2>

      {/* Portfolio selector (fixed — only one portfolio in seed data) */}
      <div className="mb-4 flex items-center gap-2">
        <span className="text-xs text-gray-400">Portfolio</span>
        <select
          disabled
          className="text-sm border border-gray-200 rounded-md px-2.5 py-1 bg-gray-50 text-gray-500 cursor-not-allowed"
        >
          <option>Portfolio 1 (demo)</option>
        </select>
      </div>

      {/* Example prompts */}
      <div className="flex flex-wrap gap-2 mb-3">
        <span className="text-xs text-gray-400 self-center">Try:</span>
        {EXAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setQuestion(p)}
            className="text-xs px-3 py-1.5 rounded-full border border-gray-300 text-gray-600 bg-white hover:border-blue-400 hover:text-blue-700 transition-colors"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Question input */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask anything about your portfolio…"
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      {/* Error */}
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {/* Loading skeleton */}
      {loading && (
        <div className="mt-5 space-y-2 animate-pulse">
          <div className="h-3 bg-gray-200 rounded w-3/4" />
          <div className="h-3 bg-gray-200 rounded w-full" />
          <div className="h-3 bg-gray-200 rounded w-5/6" />
          <div className="h-3 bg-gray-200 rounded w-2/3" />
        </div>
      )}

      {/* Answer */}
      {result && !loading && (
        <div className="mt-5 space-y-4">
          {/* Markdown answer */}
          <div className="prose prose-sm max-w-none text-gray-800 prose-p:leading-relaxed prose-li:leading-relaxed">
            <ReactMarkdown>{result.answer}</ReactMarkdown>
          </div>

          {/* Tool trace */}
          {result.tool_calls.length > 0 && (
            <details className="group border border-gray-100 rounded-lg">
              <summary className="cursor-pointer px-4 py-2.5 text-xs text-gray-400 hover:text-gray-600 select-none list-none flex items-center gap-1.5">
                <span className="group-open:rotate-90 inline-block transition-transform text-gray-300">
                  ▶
                </span>
                Tool trace &mdash;{" "}
                {result.tool_calls.length} call
                {result.tool_calls.length !== 1 ? "s" : ""}
              </summary>
              <div className="px-4 pb-4 space-y-4 border-t border-gray-100 pt-3">
                {result.tool_calls.map((tc, i) => (
                  <div key={i}>
                    <div className="font-mono text-xs font-semibold text-gray-700 mb-2">
                      {tc.name}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <div className="text-xs text-gray-400 mb-1">input</div>
                        <pre className="bg-gray-50 rounded-md p-2.5 text-xs text-gray-600 overflow-auto leading-relaxed">
                          {JSON.stringify(tc.input, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <div className="text-xs text-gray-400 mb-1">result</div>
                        <pre className="bg-gray-50 rounded-md p-2.5 text-xs text-gray-600 overflow-auto leading-relaxed">
                          {JSON.stringify(tc.result, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}

          {/* Token usage footnote */}
          <p className="text-xs text-gray-400">
            {result.usage.input_tokens} in / {result.usage.output_tokens} out tokens
          </p>
        </div>
      )}
    </section>
  );
}
