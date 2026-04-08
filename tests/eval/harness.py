"""
Eval harness — orchestrates agent runs, regex checks, tool-correctness checks,
and LLM judge calls for every golden Q&A entry.

Category-level faithfulness overrides live in CATEGORY_CONFIG so they can be
extended without touching the verdict logic.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.agent.agent import run_agent
from tests.eval.judge import judge

logger = logging.getLogger(__name__)

# ── Category-level config ─────────────────────────────────────────────────────
# Any key not listed uses the defaults.
CATEGORY_CONFIG: dict[str, dict] = {
    "D": {"faithfulness_min": 3},
}
_DEFAULTS = {"faithfulness_min": 2}


def _category_cfg(category: str) -> dict:
    return {**_DEFAULTS, **CATEGORY_CONFIG.get(category, {})}


# ── Deterministic checks ──────────────────────────────────────────────────────

def check_regex(answer: str, case: dict) -> dict[str, Any]:
    failures = []

    for pattern in case.get("regex_must_match", []):
        if not re.search(pattern, answer):
            failures.append(f"must_match pattern not found: {pattern!r}")

    for pattern in case.get("regex_must_not_match", []):
        if re.search(pattern, answer):
            failures.append(f"must_not_match pattern found: {pattern!r}")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


def check_tool_correctness(tool_log: list[dict], case: dict) -> dict[str, Any]:
    called = [t["name"] for t in tool_log]
    called_set = set(called)

    failures = []

    # All expected tools must have been called
    for tool in case.get("expected_tools", []):
        if tool not in called_set:
            failures.append(f"expected tool not called: {tool!r}")

    # Forbidden tools must not have been called
    for tool in case.get("forbidden_tools", []):
        if tool in called_set:
            failures.append(f"forbidden tool was called: {tool!r}")

    # If exact_tools, only expected tools may appear
    if case.get("exact_tools", False):
        extras = called_set - set(case.get("expected_tools", []))
        if extras:
            failures.append(f"unexpected tools called (exact_tools=true): {extras}")

    # Check expected_tool_inputs for specific cases (e.g. lookback_days=90)
    for tool_name, required_inputs in case.get("expected_tool_inputs", {}).items():
        calls_for_tool = [t for t in tool_log if t["name"] == tool_name]
        if not calls_for_tool:
            continue  # already caught by expected_tools check
        matched = False
        for call in calls_for_tool:
            actual_input = call.get("input", {})
            if all(actual_input.get(k) == v for k, v in required_inputs.items()):
                matched = True
                break
        if not matched:
            failures.append(
                f"tool {tool_name!r} not called with required inputs {required_inputs}"
            )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
    }


# ── Verdict aggregation ───────────────────────────────────────────────────────

def compute_verdict(case: dict, regex_result: dict, tool_result: dict, judge_result: dict) -> dict:
    cfg = _category_cfg(case["category"])
    faithfulness_min = cfg["faithfulness_min"]

    failures = []

    if not regex_result["passed"]:
        failures.extend(regex_result["failures"])

    if not tool_result["passed"]:
        failures.extend(tool_result["failures"])

    if judge_result.get("grounding") != "PASS":
        failures.append(f"grounding FAIL: {judge_result.get('grounding_rationale', '')}")

    faithfulness = judge_result.get("faithfulness", 0)
    if faithfulness < faithfulness_min:
        failures.append(
            f"faithfulness {faithfulness} < required {faithfulness_min} "
            f"(category {case['category']}): {judge_result.get('faithfulness_rationale', '')}"
        )

    completeness = judge_result.get("completeness", 0)
    if completeness < 2:
        failures.append(f"completeness {completeness} < 2: {judge_result.get('completeness_rationale', '')}")

    refusal = judge_result.get("refusal", "N_A")
    if refusal == "FAIL":
        failures.append(f"refusal FAIL: {judge_result.get('refusal_rationale', '')}")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "faithfulness_min_applied": faithfulness_min,
    }


# ── Main eval runner ──────────────────────────────────────────────────────────

async def run_eval(
    cases: list[dict],
    db=None,
    on_result=None,
) -> list[dict]:
    """
    Run every golden case through the agent and judge.

    Args:
        cases:     list of golden Q&A dicts (from golden_qa.json).
        db:        AsyncSession — passed to run_agent for DB-touching tools.
        on_result: optional async callback(result_dict) called after each case.

    Returns:
        list of per-case result dicts (same order as input).
    """
    results = []

    for i, case in enumerate(cases):
        case_id = case["id"]
        portfolio_id = case.get("portfolio_id")
        question = case["question"]

        # Scope the question the same way the router does
        if portfolio_id is not None:
            scoped = f"[Portfolio ID: {portfolio_id}] {question}"
        else:
            scoped = question

        logger.info("[%d/%d] Running case %s …", i + 1, len(cases), case_id)

        # ── Run agent ──────────────────────────────────────────────────────
        try:
            agent_output = await run_agent(scoped, db=db)
        except Exception as exc:
            logger.error("Agent raised for case %s: %s", case_id, exc)
            agent_output = {
                "answer": f"[Agent error: {exc}]",
                "tool_calls": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            }

        answer = agent_output["answer"]
        tool_log = agent_output["tool_calls"]

        # ── Deterministic checks ───────────────────────────────────────────
        regex_result = check_regex(answer, case)
        tool_result = check_tool_correctness(tool_log, case)

        # ── LLM judge ─────────────────────────────────────────────────────
        try:
            judge_result = await judge(scoped, tool_log, answer)
        except Exception as exc:
            logger.error("Judge raised for case %s: %s", case_id, exc)
            judge_result = {
                "grounding": "FAIL",
                "grounding_rationale": f"Judge error: {exc}",
                "faithfulness": 1,
                "faithfulness_rationale": f"Judge error: {exc}",
                "completeness": 1,
                "completeness_rationale": f"Judge error: {exc}",
                "refusal": "N_A",
                "refusal_rationale": "",
                "judge_input_tokens": 0,
                "judge_output_tokens": 0,
            }

        # ── Verdict ────────────────────────────────────────────────────────
        verdict = compute_verdict(case, regex_result, tool_result, judge_result)

        result = {
            "id": case_id,
            "category": case["category"],
            "question": question,
            "portfolio_id": portfolio_id,
            "scoped_question": scoped,
            "answer": answer,
            "tool_log": tool_log,
            "eval": {
                "regex": regex_result,
                "tool_correctness": tool_result,
                "grounding": judge_result.get("grounding"),
                "grounding_rationale": judge_result.get("grounding_rationale"),
                "faithfulness": judge_result.get("faithfulness"),
                "faithfulness_rationale": judge_result.get("faithfulness_rationale"),
                "faithfulness_min": verdict["faithfulness_min_applied"],
                "completeness": judge_result.get("completeness"),
                "completeness_rationale": judge_result.get("completeness_rationale"),
                "refusal": judge_result.get("refusal"),
                "refusal_rationale": judge_result.get("refusal_rationale"),
                "verdict": "PASS" if verdict["passed"] else "FAIL",
                "failure_reasons": verdict["failures"],
            },
            "usage": {
                "agent_input_tokens": agent_output["usage"].get("input_tokens", 0),
                "agent_output_tokens": agent_output["usage"].get("output_tokens", 0),
                "judge_input_tokens": judge_result.get("judge_input_tokens", 0),
                "judge_output_tokens": judge_result.get("judge_output_tokens", 0),
            },
        }

        results.append(result)

        status = "✓" if verdict["passed"] else "✗"
        logger.info(
            "  %s %s | faith=%s complete=%s tool_correct=%s grounding=%s",
            status, case_id,
            judge_result.get("faithfulness"),
            judge_result.get("completeness"),
            "PASS" if tool_result["passed"] else "FAIL",
            judge_result.get("grounding"),
        )

        if on_result:
            await on_result(result)

    return results


def build_summary(results: list[dict], run_id: str) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r["eval"]["verdict"] == "PASS")

    # Per-category stats
    per_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"]
        if cat not in per_category:
            per_category[cat] = {"total": 0, "passed": 0}
        per_category[cat]["total"] += 1
        if r["eval"]["verdict"] == "PASS":
            per_category[cat]["passed"] += 1

    for cat, stats in per_category.items():
        stats["pass_rate"] = round(stats["passed"] / stats["total"], 3)

    # Tool correctness rate
    tool_correct = sum(1 for r in results if r["eval"]["tool_correctness"]["passed"])

    # Faithfulness avg (exclude cases where grounding failed — score is unreliable)
    faith_scores = [
        r["eval"]["faithfulness"]
        for r in results
        if r["eval"]["grounding"] == "PASS" and r["eval"]["faithfulness"] is not None
    ]
    faith_avg = round(sum(faith_scores) / len(faith_scores), 2) if faith_scores else None

    # Token cost
    total_agent_in  = sum(r["usage"]["agent_input_tokens"] for r in results)
    total_agent_out = sum(r["usage"]["agent_output_tokens"] for r in results)
    total_judge_in  = sum(r["usage"]["judge_input_tokens"] for r in results)
    total_judge_out = sum(r["usage"]["judge_output_tokens"] for r in results)

    failures = [r["id"] for r in results if r["eval"]["verdict"] == "FAIL"]

    return {
        "run_id": run_id,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3),
        "ci_tool_correctness_rate": round(tool_correct / total, 3),
        "ci_gate_met": (tool_correct == total) and (passed / total >= 0.85),
        "faithfulness_avg": faith_avg,
        "per_category": per_category,
        "failures": failures,
        "token_usage": {
            "agent_input": total_agent_in,
            "agent_output": total_agent_out,
            "judge_input": total_judge_in,
            "judge_output": total_judge_out,
        },
    }
