"""Run a match (simulated or replayed) into a minute-by-minute timeline the coach
dashboard can play back, and the SSE endpoint can stream."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from ..models import Club, Player
from .analyzer import analyze
from .bench import recommend_substitutions
from .models import Event, MatchState
from .simulator import bench, simulate_match, starting_xi


def build_timeline(
    home: Club,
    away: Club,
    events: Optional[Iterable[Event]] = None,
    focus: Optional[str] = None,
    pool: Optional[dict[str, Player]] = None,
    step: float = 1.0,
    seed: int = 4,
) -> dict[str, Any]:
    focus = focus or home.club_id
    focus_club = home if focus == home.club_id else away
    events = list(events) if events is not None else list(simulate_match(home, away, seed=seed))
    state = MatchState(home.club_id, away.club_id)
    xi_h, xi_a = starting_xi(home), starting_xi(away)
    for p in xi_h:
        state.player(home.club_id, p.name, p.position)
    for p in xi_a:
        state.player(away.club_id, p.name, p.position)
    frames: list[dict[str, Any]] = []
    seen: dict[str, float] = {}
    next_tick = step
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.minute <= next_tick:
            state.apply(ev)
            i += 1
            continue
        state.minute = next_tick
        frame = _frame(state, focus, focus_club, pool, seen)
        frames.append(frame)
        next_tick += step
    state.minute = max(state.minute, next_tick)
    frames.append(_frame(state, focus, focus_club, pool, seen))
    return {
        "home": {
            "id": home.club_id,
            "name": home.short_name,
            "formation": home.formation,
            "coach": home.coach_name,
        },
        "away": {
            "id": away.club_id,
            "name": away.short_name,
            "formation": away.formation,
            "coach": away.coach_name,
        },
        "focus": focus,
        "xi": {
            home.club_id: [{"name": p.name, "pos": p.position, "age": p.age} for p in xi_h],
            away.club_id: [{"name": p.name, "pos": p.position, "age": p.age} for p in xi_a],
        },
        "bench": {
            home.club_id: [
                {"name": p.name, "pos": p.position, "age": p.age, "role": p.role}
                for p in bench(home, xi_h)
            ],
            away.club_id: [
                {"name": p.name, "pos": p.position, "age": p.age, "role": p.role}
                for p in bench(away, xi_a)
            ],
        },
        "frames": frames,
        "events_sample": [e.to_dict() for e in events[:50]],
        "simulated": True,
        "note": "SİMÜLE EDİLMİŞ event akışı: iki kulüp dosyasından tohumlanmış senaryo. Üretimde aynı Event şemasına lisanslı canlı besleme (Opta/Stats Perform, StatsBomb, Second Spectrum) bağlanır.",
    }


def _frame(
    state: MatchState, focus: str, focus_club: Club, pool, seen: dict[str, float]
) -> dict[str, Any]:
    snap = state.snapshot()
    insights = analyze(state, focus)
    fresh = []
    for ins in insights:
        key = ins.key + ":" + ",".join(ins.players) + ":" + str(ins.metrics.get("lane", ""))
        last = seen.get(key)
        if (
            last is None
            or state.minute - last >= 10
            or (ins.severity == "act" and last is not None and state.minute - last >= 5)
        ):
            seen[key] = state.minute
            d = ins.to_dict()
            if ins.severity in ("act", "watch") and ins.kind in ("weakness", "fatigue", "risk"):
                d["subs"] = [
                    r.to_dict()
                    for r in recommend_substitutions(state, focus, focus_club, ins, pool)
                ]
            fresh.append(d)
    lite = {
        "minute": snap["minute"],
        "score": snap["score"],
        "teams": {
            t: {k: v for k, v in snap["teams"][t].items() if k != "players"} for t in snap["teams"]
        },
        "players": {t: [p for p in snap["teams"][t]["players"]] for t in snap["teams"]},
        "insights": fresh,
        "log": snap["log"][-6:],
    }
    return lite
