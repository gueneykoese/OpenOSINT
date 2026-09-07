"""Bench recommendations: who on the bench addresses an insight, and why.

Scoring (0-100):
* position fit 40 — exact position, then neighbours
* trait fit 30 — the insight's required traits vs what we know about the player
  (style tags from our player pool when we represent him; otherwise position defaults)
* freshness / game state 30 — minutes unused, age curve, score-line urgency

Everything explains itself; nothing is hidden inside a model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..models import POSITION_NEIGHBOURS, Club, Player, SquadPlayer
from .analyzer import Insight
from .models import MatchState

# What a position typically brings when we know nothing else about the player.
_POS_TRAITS = {
    "GK": ["distribution"],
    "CB": ["aerial", "defensive", "tall"],
    "LB": ["pace", "defensive", "1v1 defending", "stamina"],
    "RB": ["pace", "defensive", "1v1 defending", "stamina"],
    "DM": ["ball-winning", "pressing", "defensive", "stamina"],
    "CM": ["pressing", "stamina", "link play"],
    "AM": ["creative", "link play", "between the lines"],
    "LW": ["pace", "1v1", "pressing"],
    "RW": ["pace", "1v1", "pressing"],
    "ST": ["finishing", "pressing", "aerial"],
}
_TAG_SYNONYMS = {
    "pace": ["pace", "quick", "fast", "sprint", "runs in behind", "athletic"],
    "pressing": ["press", "pressing", "work rate", "counter-press"],
    "ball-winning": ["ball-winning", "tackl", "intercept", "no. 6", "no.6", "destroyer"],
    "defensive": ["defensive", "defender", "front-foot defender", "disciplin"],
    "1v1 defending": ["1v1", "one-on-one", "duel"],
    "aerial": ["aerial", "header", "tall", "dominant"],
    "tall": ["tall", "190", "aerial"],
    "creative": ["creative", "playmaker", "no. 10", "no.10", "key pass", "assist"],
    "link play": ["link", "between the lines", "second striker", "false"],
    "between the lines": ["between the lines", "pockets", "no. 10"],
    "stamina": ["stamina", "engine", "box-to-box", "work rate"],
    "finishing": ["finish", "poacher", "goals", "penalty-box"],
    "distribution": ["distribution", "sweeper"],
}


@dataclass
class SubRecommendation:
    player: str
    position: str
    score: float
    reasons: list[str]
    replaces: Optional[str] = None
    represented_by_us: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _traits_for(sp: SquadPlayer, pool: dict[str, Player]) -> tuple[list[str], bool]:
    """Known traits: from our player pool when the player is one of ours, else position defaults."""
    for p in pool.values():
        if p.name.lower() == sp.name.lower():
            return p.style_tags, True
    return [], False


def _trait_fit(required: list[str], tags: list[str], position: str) -> tuple[float, list[str]]:
    if not required:
        return 0.6, []
    hits = []
    text = " ".join(tags).lower()
    defaults = _POS_TRAITS.get(position, [])
    for r in required:
        syns = _TAG_SYNONYMS.get(r, [r])
        if tags and any(s in text for s in syns):
            hits.append(r)
        elif not tags and r in defaults:
            hits.append(r + "*")
    return len(hits) / len(required), hits


def recommend_substitutions(
    state: MatchState,
    team: str,
    club: Club,
    insight: Insight,
    pool: Optional[dict[str, Player]] = None,
    limit: int = 3,
) -> list[SubRecommendation]:
    pool = pool or {}
    used = {p.name for p in state.players.values() if p.team == team}
    on_pitch = {p.name: p for p in state.on_pitch(team)}
    bench = [
        p
        for p in club.squad
        if p.name not in used
        and not p.injury_flag
        and (p.position != "GK" or insight.position == "GK")
    ]
    need_pos = insight.position
    score_diff = state.score[team] - state.score[state.opponent(team)]
    losing, winning = score_diff < 0, score_diff > 0
    out: list[SubRecommendation] = []
    for sp in bench:
        reasons: list[str] = []
        # position
        if need_pos is None:
            pos_fit = 0.6
        elif sp.position == need_pos:
            pos_fit = 1.0
            reasons.append(f"tam pozisyon ({need_pos})")
        elif need_pos in POSITION_NEIGHBOURS.get(
            sp.position, set()
        ) or sp.position in POSITION_NEIGHBOURS.get(need_pos, set()):
            pos_fit = 0.6
            reasons.append(f"komşu pozisyon ({sp.position} → {need_pos})")
        else:
            pos_fit = 0.15
        tags, ours = _traits_for(sp, pool)
        t_fit, hits = _trait_fit(insight.traits, tags, sp.position)
        if pos_fit < 0.5:
            t_fit *= 0.4  # right traits in the wrong position rarely fix the problem
        if hits:
            reasons.append(
                "özellikler: "
                + ", ".join(hits)
                + ("" if all(h.endswith("*") for h in hits) is False else " (pozisyon varsayımı)")
            )
        # freshness & game state
        fresh = 1.0
        if sp.age is not None:
            if sp.age >= 33:
                fresh -= 0.15
            elif sp.age <= 22:
                fresh -= 0.05  # inexperience in a hot game
        gs = 0.5
        attacking = sp.position in ("ST", "LW", "RW", "AM")
        if losing and attacking:
            gs = 1.0
            reasons.append("geride: hücum etkisi")
        elif winning and sp.position in ("CB", "DM", "LB", "RB"):
            gs = 1.0
            reasons.append("önde: oyunu kilitleme")
        elif not losing and not winning:
            gs = 0.7
        if insight.kind == "fatigue" and sp.position == need_pos:
            gs = max(gs, 0.9)
        total = round(40 * pos_fit + 30 * t_fit + 30 * (0.6 * fresh + 0.4 * gs), 1)
        if ours:
            reasons.append("temsil ettiğimiz oyuncu: stil etiketleri kaynaklı")
        # whom to replace
        repl = None
        if insight.players:
            repl = insight.players[0]
        elif need_pos:
            cands = [p for p in on_pitch.values() if p.position == need_pos]
            if cands:
                repl = max(cands, key=lambda p: p.fatigue(state.minute)).name
        out.append(
            SubRecommendation(
                sp.name,
                sp.position,
                total,
                reasons,
                repl,
                ours,
                {"age": sp.age, "role": sp.role, "pos_fit": pos_fit, "trait_fit": round(t_fit, 2)},
            )
        )
    out.sort(key=lambda r: r.score, reverse=True)
    return out[:limit]
