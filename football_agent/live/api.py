"""FastAPI router: live match intelligence.

* GET  /live/matches                       → available club pairs (from the dossier set)
* GET  /live/{home}/{away}/timeline        → full precomputed timeline (simulated feed)
* GET  /live/{home}/{away}/stream          → Server-Sent Events, one frame per simulated minute
* POST /live/{home}/{away}/events          → push real events (adapter for a licensed feed);
                                             returns current insights + bench recommendations
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from .analyzer import analyze
from .bench import recommend_substitutions
from .models import Event, MatchState
from .timeline import build_timeline

router = APIRouter(prefix="/live", tags=["live"])
_LIVE: dict[str, MatchState] = {}  # in-memory live states keyed "home:away" (production: Redis)


def _engine():
    from ..api import engine

    return engine()


def _clubs(home: str, away: str):
    e = _engine()
    if home not in e.clubs or away not in e.clubs:
        raise HTTPException(404, "unknown club")
    return e, e.clubs[home], e.clubs[away]


@router.get("/matches")
def matches() -> list[dict[str, Any]]:
    e = _engine()
    out = []
    for c in e.clubs.values():
        for opp in c.ucl.get("opponents_home") or []:
            match = next(
                (
                    o
                    for o in e.clubs.values()
                    if o.short_name.lower() in opp.lower() or opp.lower() in o.name.lower()
                ),
                None,
            )
            if match:
                out.append(
                    {
                        "home": c.club_id,
                        "away": match.club_id,
                        "label": f"{c.short_name} v {match.short_name}",
                    }
                )
    return out


@router.get("/{home}/{away}/timeline")
def timeline(home: str, away: str, focus: Optional[str] = None, seed: int = 4) -> dict[str, Any]:
    e, h, a = _clubs(home, away)
    return build_timeline(h, a, focus=focus or home, pool=e.players, seed=seed)


@router.get("/{home}/{away}/stream")
async def stream(
    home: str, away: str, focus: Optional[str] = None, seed: int = 4, speed: float = 1.0
):
    e, h, a = _clubs(home, away)
    tl = build_timeline(h, a, focus=focus or home, pool=e.players, seed=seed)

    async def gen():
        for frame in tl["frames"]:
            yield {"event": "frame", "data": json.dumps(frame, ensure_ascii=False)}
            await asyncio.sleep(max(0.05, 1.0 / speed))
        yield {"event": "end", "data": "{}"}

    return EventSourceResponse(gen())


@router.post("/{home}/{away}/events")
def push_events(
    home: str, away: str, events: list[dict[str, Any]], focus: Optional[str] = None
) -> dict[str, Any]:
    """Adapter entry point for a real feed: post Event dicts, get insights back."""
    e, h, a = _clubs(home, away)
    key = f"{home}:{away}"
    st = _LIVE.setdefault(key, MatchState(home, away))
    for d in events:
        st.apply(Event(**{k: v for k, v in d.items() if k in Event.__dataclass_fields__}))
    focus = focus or home
    club = h if focus == home else a
    ins = analyze(st, focus)
    return {
        "state": st.snapshot(),
        "insights": [
            i.to_dict()
            | (
                {
                    "subs": [
                        r.to_dict() for r in recommend_substitutions(st, focus, club, i, e.players)
                    ]
                }
                if i.severity != "info"
                else {}
            )
            for i in ins
        ],
    }


@router.delete("/{home}/{away}/events")
def reset(home: str, away: str) -> dict[str, str]:
    _LIVE.pop(f"{home}:{away}", None)
    return {"status": "reset"}
