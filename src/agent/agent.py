"""
LLM agent loop — Milestone 2.

Implements the Anthropic tool-use agentic loop:
  1. Send user message + tool schemas to Claude.
  2. While stop_reason == "tool_use":
       a. Collect all tool_use blocks from the response.
       b. Dispatch each tool and collect results.
       c. Append the assistant turn + tool_result turn to messages.
       d. Re-send to Claude.
  3. Return the final text response and usage metadata.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.tools import TOOL_SCHEMAS, dispatch
from src.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a portfolio risk analyst assistant.
You have access to tools that can score portfolios, retrieve holdings, \
explain risk metrics, and suggest rebalancing.

Guidelines:
- Always call get_health_score before discussing risk levels.
- When explaining a feature value, call explain_feature with the actual numeric value.
- Be concise and quantitative. Back every claim with a number from the tools.
- If the user asks for rebalancing, call suggest_rebalance and present the diff clearly.
- Rebalancing honesty: when suggest_rebalance returns target_reachable=false, you MUST \
state the best_achievable_score from the tool result and never claim the target was met. \
Do not round up, estimate, or use "~" to imply a target was reached when it was not.
- Missing tools: if the user asks for something you have no tool for (e.g. live price \
lookups, news, weather), explicitly say "I don't have a tool for that" rather than \
ignoring that part of the question or fabricating an answer.
"""


async def run_agent(
    question: str,
    db: AsyncSession | None = None,
    max_turns: int = 10,
) -> dict[str, Any]:
    """
    Run the agentic loop for a single user question.

    Returns:
        {
            "answer": str,
            "tool_calls": [{"name": str, "input": dict, "result": dict}],
            "usage": {"input_tokens": int, "output_tokens": int},
        }
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    messages: list[dict] = [{"role": "user", "content": question}]
    tool_call_log: list[dict] = []
    total_input_tokens = 0
    total_output_tokens = 0

    for turn in range(max_turns):
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        total_input_tokens += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens

        logger.debug(
            "Turn %d | stop_reason=%s | tokens in=%d out=%d",
            turn,
            response.stop_reason,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        if response.stop_reason == "end_turn":
            answer = _extract_text(response.content)
            return {
                "answer": answer,
                "tool_calls": tool_call_log,
                "usage": {
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
            }

        if response.stop_reason == "tool_use":
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

            # Append the full assistant turn (may contain text + tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Dispatch all tool calls and collect results
            tool_results = []
            for block in tool_use_blocks:
                logger.info("Calling tool: %s(%s)", block.name, block.input)
                result = await dispatch(block.name, block.input, db=db)
                tool_call_log.append({"name": block.name, "input": block.input, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason (e.g. max_tokens)
        logger.warning("Unexpected stop_reason: %s", response.stop_reason)
        break

    return {
        "answer": "Agent reached maximum turns without a final answer.",
        "tool_calls": tool_call_log,
        "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens},
    }


def _extract_text(content: list) -> str:
    return " ".join(block.text for block in content if hasattr(block, "text")).strip()
