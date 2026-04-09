"""
Integration tests for the agentic loop.

The Anthropic client is fully mocked — no API key needed.
Tests assert tool dispatch, message threading, and response shape.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.agent import run_agent


def _make_response(stop_reason: str, content: list) -> MagicMock:
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content
    resp.usage = MagicMock(input_tokens=100, output_tokens=50)
    return resp


def _text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(tool_id: str, name: str, input_: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_
    return block


@pytest.mark.asyncio
async def test_agent_direct_text_response():
    """Claude returns text immediately — no tool calls."""
    text_resp = _make_response("end_turn", [_text_block("Here is my answer.")])

    with patch("src.agent.agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=text_resp)

        result = await run_agent("What time is it?", db=None)

    assert result["answer"] == "Here is my answer."
    assert result["tool_calls"] == []
    assert result["usage"]["input_tokens"] == 100


@pytest.mark.asyncio
async def test_agent_single_tool_call():
    """Claude calls explain_feature once then returns text."""
    tool_block = _tool_use_block(
        "tu_001", "explain_feature",
        {"feature_name": "sharpe", "feature_value": 0.3},
    )
    tool_resp   = _make_response("tool_use",  [tool_block])
    final_resp  = _make_response("end_turn",  [_text_block("The Sharpe ratio is poor.")])

    with patch("src.agent.agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=[tool_resp, final_resp])

        result = await run_agent("Explain my Sharpe ratio of 0.3", db=None)

    assert "poor" in result["answer"]
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "explain_feature"
    assert "error" not in result["tool_calls"][0]["result"]


@pytest.mark.asyncio
async def test_agent_tool_result_threaded_correctly():
    """Verify messages list has assistant turn + tool_result turn before final call."""
    tool_block = _tool_use_block(
        "tu_002", "explain_feature",
        {"feature_name": "volatility", "feature_value": 0.35},
    )
    tool_resp  = _make_response("tool_use", [tool_block])
    final_resp = _make_response("end_turn", [_text_block("Volatility is high.")])

    captured_calls = []

    async def capture_create(**kwargs):
        captured_calls.append(kwargs["messages"])
        if len(captured_calls) == 1:
            return tool_resp
        return final_resp

    with patch("src.agent.agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = capture_create

        await run_agent("How bad is 35% volatility?", db=None)

    # Second call must have: user, assistant (tool_use), user (tool_result)
    second_call_messages = captured_calls[1]
    assert second_call_messages[1]["role"] == "assistant"
    assert second_call_messages[2]["role"] == "user"
    tool_result_content = second_call_messages[2]["content"]
    assert tool_result_content[0]["type"] == "tool_result"
    assert tool_result_content[0]["tool_use_id"] == "tu_002"


@pytest.mark.asyncio
async def test_agent_max_turns_guard():
    """Agent stops after max_turns without infinite looping."""
    always_tool = _make_response(
        "tool_use",
        [_tool_use_block("tu_x", "explain_feature", {"feature_name": "sharpe", "feature_value": 1.0})],  # noqa: E501
    )

    with patch("src.agent.agent.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=always_tool)

        result = await run_agent("Loop forever", db=None, max_turns=3)

    assert "maximum turns" in result["answer"]
    assert mock_client.messages.create.call_count == 3
