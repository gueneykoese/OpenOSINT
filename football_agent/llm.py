"""Optional Claude layer: turns a deterministic MatchResult into a scouting memo
and stress-tests it. The numeric score never comes from the model — the model
only explains, challenges and drafts. Requires ANTHROPIC_API_KEY (or an
`ant auth login` profile); without credentials `narrate()` returns a
deterministic fallback so the API and CLI keep working offline."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from .models import Club, MatchResult, Player

MODEL = os.environ.get("FOOTBALL_AGENT_MODEL", "claude-opus-5")

SYSTEM = """You are the analysis layer of an AI-assisted football player-agency.
You receive (1) a club dossier, (2) a player dossier and (3) a deterministic match
score with per-dimension explanations, all built from public, sourced data.

Your job:
- Write a concise scouting memo (max 250 words) for the agency's human negotiator.
- Explicitly challenge the score: name the single strongest reason the deal fails.
- Never invent statistics. If a number is missing, say it is missing.
- Treat mental, off-pitch and political/social information as *context to brief the
  parties on*, never as a verdict about a person. Do not speculate about private life.
- Output JSON with keys: memo (string), biggest_risk (string), questions_for_club
  (array of strings), questions_for_player (array of strings), recommended_action
  (one of: approach_now, monitor, pass)."""


def _client() -> Optional[Any]:
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return None
    return anthropic.Anthropic()


def _fallback(result: MatchResult) -> dict[str, Any]:
    weakest = min(result.dimensions, key=lambda d: d.score)
    action = {
        "strong match": "approach_now",
        "good match": "approach_now",
        "possible": "monitor",
    }.get(result.verdict, "pass")
    return {
        "memo": result.summary + " (Offline memo: set ANTHROPIC_API_KEY for the full narrative.)",
        "biggest_risk": f"{weakest.label}: {weakest.explanation}",
        "questions_for_club": [
            f"Confirm the stated need at {result.position} and the real budget."
        ],
        "questions_for_player": [
            "Confirm openness to the move and any family/relocation constraints."
        ],
        "recommended_action": action,
        "generated_by": "fallback",
    }


def narrate(result: MatchResult, player: Player, club: Club) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback(result)
    payload = {
        "club": {k: v for k, v in club.raw.items() if k not in ("squad",)},
        "club_squad_same_position": [
            p.__dict__ | {"stats": p.stats.__dict__} for p in club.players_in(result.position)
        ],
        "player": player.raw,
        "match": result.to_dict(),
    }
    try:
        import anthropic

        resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            messages=[
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)}
            ],
        )
        if resp.stop_reason == "refusal":
            out = _fallback(result)
            out["generated_by"] = "fallback:refusal"
            return out
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        start, end = text.find("{"), text.rfind("}")
        data = json.loads(text[start : end + 1]) if start >= 0 else {"memo": text}
        data["generated_by"] = MODEL
        return data
    except (anthropic.APIError, json.JSONDecodeError, ValueError) as exc:  # type: ignore[name-defined]
        out = _fallback(result)
        out["generated_by"] = f"fallback:{type(exc).__name__}"
        return out
