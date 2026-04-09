"""
CLI entry point for the eval harness.

Usage:
    python -m scripts.run_eval                        # all 31 cases (full tier)
    python -m scripts.run_eval --tier smoke           # 5 smoke cases, gate ≥80%
    python -m scripts.run_eval --tier full            # all 31 cases, gate ≥85%
    python -m scripts.run_eval --ids A1 B3 F1         # specific cases
    python -m scripts.run_eval --categories A B       # specific categories
    python -m scripts.run_eval --dry-run              # print cases, no API calls
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.db.session import AsyncSessionLocal
from tests.eval.harness import build_summary, run_eval

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

GOLDEN_QA_PATH = Path("tests/eval/golden_qa.json")
EVAL_RUNS_DIR  = Path("eval_runs")

# Representative cases covering each major capability area.
# Chosen to be fast (~2 min) while catching the most common regressions.
SMOKE_CASE_IDS: list[str] = ["A1", "B1", "D1", "F1", "E1"]

TIER_CONFIG: dict[str, dict] = {
    "smoke": {"case_ids": SMOKE_CASE_IDS, "pass_rate_threshold": 0.80},
    "full":  {"case_ids": None,           "pass_rate_threshold": 0.85},
}


def load_cases(
    tier: str,
    ids: list[str] | None,
    categories: list[str] | None,
) -> tuple[list[dict], float]:
    """Return (cases, pass_rate_threshold).

    --tier restricts the default case set; --ids / --categories further filter it.
    If --ids or --categories are provided they take precedence over the tier preset.
    """
    all_cases = json.loads(GOLDEN_QA_PATH.read_text())
    cfg = TIER_CONFIG[tier]

    # Tier preset (only applied when no explicit id/category filter given)
    if not ids and not categories and cfg["case_ids"] is not None:
        all_cases = [c for c in all_cases if c["id"] in cfg["case_ids"]]

    if ids:
        all_cases = [c for c in all_cases if c["id"] in ids]
    if categories:
        all_cases = [c for c in all_cases if c["category"] in categories]

    return all_cases, cfg["pass_rate_threshold"]


async def main(args: argparse.Namespace) -> int:
    cases, pass_rate_threshold = load_cases(args.tier, args.ids, args.categories)
    if not cases:
        logger.error("No cases matched the given filters.")
        return 1

    logger.info(
        "Tier: %s | Cases: %d | Pass-rate gate: %.0f%%",
        args.tier, len(cases), pass_rate_threshold * 100,
    )

    if args.dry_run:
        for c in cases:
            print(f"  {c['id']} [{c['category']}] {c['question'][:80]}")
        return 0

    # ── Output directory ──────────────────────────────────────────────────
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = EVAL_RUNS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    summary_path = out_dir / "summary.json"

    logger.info("Run ID: %s  →  %s", run_id, out_dir)

    # ── Write results as they come in ─────────────────────────────────────
    results_file = results_path.open("w")

    async def on_result(result: dict) -> None:
        results_file.write(json.dumps(result) + "\n")
        results_file.flush()

    # ── Run ───────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        results = await run_eval(cases, db=db, on_result=on_result)

    results_file.close()

    # ── Summary ───────────────────────────────────────────────────────────
    summary = build_summary(results, run_id, pass_rate_threshold=pass_rate_threshold)
    summary_path.write_text(json.dumps(summary, indent=2))

    # ── Print summary to stdout ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Run:       {run_id}  [{args.tier} tier]")
    print(f"  Total:     {summary['passed']}/{summary['total']} passed  ({summary['pass_rate']*100:.1f}%)")
    print(f"  Gate:      ≥{pass_rate_threshold*100:.0f}%")
    print(f"  Tool corr: {summary['ci_tool_correctness_rate']*100:.1f}%")
    print(f"  Faith avg: {summary['faithfulness_avg']}")
    print(f"  CI gate:   {'✓ MET' if summary['ci_gate_met'] else '✗ NOT MET'}")
    print()

    if summary["failures"]:
        print("  Failures:")
        for fid in summary["failures"]:
            r = next(r for r in results if r["id"] == fid)
            reasons = r["eval"]["failure_reasons"]
            print(f"    {fid}: {reasons[0] if reasons else '(unknown)'}")

    print()
    print("  Per-category:")
    for cat, stats in sorted(summary["per_category"].items()):
        bar = "✓" * stats["passed"] + "✗" * (stats["total"] - stats["passed"])
        print(f"    {cat}: {stats['passed']}/{stats['total']}  {bar}")

    print("=" * 60)
    print(f"\n  results.jsonl → {results_path}")
    print(f"  summary.json  → {summary_path}\n")

    return 0 if summary["ci_gate_met"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the portfolio agent eval harness.")
    parser.add_argument(
        "--tier",
        choices=["smoke", "full"],
        default="full",
        help="smoke: 5 representative cases, gate ≥80%%; full: all 31 cases, gate ≥85%% (default)",
    )
    parser.add_argument("--ids",        nargs="*", help="Specific case IDs to run")
    parser.add_argument("--categories", nargs="*", help="Categories to run (A B C D E F G)")
    parser.add_argument("--dry-run",    action="store_true", help="Print cases without running")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args)))
