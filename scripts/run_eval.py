"""
CLI entry point for the eval harness.

Usage:
    python -m scripts.run_eval                        # all 31 cases
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


def load_cases(ids: list[str] | None, categories: list[str] | None) -> list[dict]:
    cases = json.loads(GOLDEN_QA_PATH.read_text())
    if ids:
        cases = [c for c in cases if c["id"] in ids]
    if categories:
        cases = [c for c in cases if c["category"] in categories]
    return cases


async def main(args: argparse.Namespace) -> int:
    cases = load_cases(args.ids, args.categories)
    if not cases:
        logger.error("No cases matched the given filters.")
        return 1

    logger.info("Loaded %d cases.", len(cases))

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
    summary = build_summary(results, run_id)
    summary_path.write_text(json.dumps(summary, indent=2))

    # ── Print summary to stdout ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  Run: {run_id}")
    print(f"  Total:     {summary['passed']}/{summary['total']} passed  ({summary['pass_rate']*100:.1f}%)")
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
    parser.add_argument("--ids",        nargs="*", help="Specific case IDs to run")
    parser.add_argument("--categories", nargs="*", help="Categories to run (A B C D E F G)")
    parser.add_argument("--dry-run",    action="store_true", help="Print cases without running")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args)))
