# tests/test_output_limits.py
"""Tests for the per-result output cap that protects the LLM context window."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from openosint import agent as agent_mod
from openosint import mcp_server
from openosint.output_limits import DEFAULT_MAX_OUTPUT_CHARS, max_output_chars, truncate_output


def test_short_text_untouched():
    assert truncate_output("hello") == "hello"


def test_exact_limit_untouched():
    text = "x" * 100
    assert truncate_output(text, limit=100) == text


def test_long_text_truncated_with_trailer():
    text = "\n".join(f"line {i}" for i in range(2000))
    out = truncate_output(text, limit=500)
    assert len(out) < len(text)
    assert "[output truncated:" in out
    assert "OPENOSINT_MAX_OUTPUT_CHARS" in out
    # Cut lands on a line boundary, not mid-line.
    body = out.split("\n\n[output truncated")[0]
    assert body.endswith(tuple(f"line {i}" for i in range(2000)))


def test_zero_limit_disables():
    text = "y" * 50_000
    assert truncate_output(text, limit=0) == text


def test_env_override(monkeypatch):
    monkeypatch.setenv("OPENOSINT_MAX_OUTPUT_CHARS", "250")
    assert max_output_chars() == 250
    assert len(truncate_output("z" * 1000)) < 400


def test_env_invalid_falls_back(monkeypatch):
    monkeypatch.setenv("OPENOSINT_MAX_OUTPUT_CHARS", "lots")
    assert max_output_chars() == DEFAULT_MAX_OUTPUT_CHARS


def test_mcp_call_tool_caps_result(monkeypatch):
    monkeypatch.setenv("OPENOSINT_MAX_OUTPUT_CHARS", "300")
    big = "[+] sub.example.com\n" * 500
    handler = AsyncMock(return_value=big)
    with patch.dict(mcp_server._HANDLERS, {"search_domain": (handler, lambda a: a["domain"])}):
        result = asyncio.run(mcp_server.call_tool("search_domain", {"domain": "example.com"}))
    text = result.content[0].text
    assert result.isError is False
    assert len(text) < 500
    assert "[output truncated:" in text


def test_agent_execute_tool_caps_result(monkeypatch):
    monkeypatch.setenv("OPENOSINT_MAX_OUTPUT_CHARS", "300")
    big = "page content " * 5000
    with patch.dict(agent_mod._TOOL_MAP, {"scrape_url": AsyncMock(return_value=big)}):
        out = asyncio.run(agent_mod._execute_tool("scrape_url", {"url": "https://x"}, None))
    assert len(out) < 500
    assert "[output truncated:" in out


def test_anthropic_agent_stops_after_max_rounds():
    """A model that never stops calling tools must not loop forever."""

    class _Block:
        type = "tool_use"
        id = "t1"
        name = "generate_dorks"
        input = {"target": "x"}

    class _Resp:
        stop_reason = "tool_use"
        content = [_Block()]

    with patch.dict(agent_mod._TOOL_MAP, {"generate_dorks": AsyncMock(return_value="ok")}):
        ag = agent_mod.OpenOSINTAgent(api_key="test")
        ag.client = AsyncMock()
        ag.client.messages.create = AsyncMock(return_value=_Resp())
        resp = asyncio.run(ag.run("investigate x"))

    assert resp.error == agent_mod._TOOL_ROUNDS_EXCEEDED
    assert ag.client.messages.create.await_count == agent_mod._MAX_TOOL_ROUNDS + 1
    # Caching is requested on every call so the tools+system prefix is reused.
    kwargs = ag.client.messages.create.await_args.kwargs
    assert kwargs["cache_control"] == {"type": "ephemeral"}


if __name__ == "__main__":
    pytest.main([__file__])
