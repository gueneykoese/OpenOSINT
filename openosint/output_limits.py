# openosint/output_limits.py
"""
Caps on how much text a single tool result may push into an LLM context.

Every tool result the MCP server or the built-in agent returns lands verbatim
in the calling model's context window and is re-sent on every subsequent turn
of that conversation. Uncapped results (a full web page from ``scrape_url``,
a whole ``graph_export``, hundreds of subdomains) are the single biggest
driver of token consumption — and, for Claude Code / claude.ai subscribers,
of how fast the usage limit drains.

``OPENOSINT_MAX_OUTPUT_CHARS`` overrides the default cap (set it to ``0`` to
disable truncation entirely).
"""

from __future__ import annotations

import os

# ~4k tokens. Large enough for any normal tool result, small enough that a
# runaway page fetch or graph dump cannot flood the context.
DEFAULT_MAX_OUTPUT_CHARS = 16_000

_ENV_VAR = "OPENOSINT_MAX_OUTPUT_CHARS"


def max_output_chars() -> int:
    """Return the configured cap (chars). ``0`` or a negative value disables it."""
    raw = os.environ.get(_ENV_VAR, "").strip()
    if not raw:
        return DEFAULT_MAX_OUTPUT_CHARS
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_MAX_OUTPUT_CHARS


def truncate_output(text: str, limit: int | None = None) -> str:
    """
    Return *text* cut to at most *limit* characters, with a trailer that tells
    the model how much was dropped so it never mistakes a cut for the end.

    The cut is made at the last line break inside the budget when one exists
    reasonably close to it, so partial lines are not left dangling.
    """
    cap = max_output_chars() if limit is None else limit
    if cap <= 0 or len(text) <= cap:
        return text

    head = text[:cap]
    newline = head.rfind("\n")
    if newline >= cap // 2:
        head = head[:newline]
    dropped = len(text) - len(head)
    return (
        f"{head.rstrip()}\n\n"
        f"[output truncated: {dropped:,} of {len(text):,} characters omitted "
        f"— narrow the query or raise {_ENV_VAR}]"
    )
