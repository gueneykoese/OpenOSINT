"""Event schema and rolling match state."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

WINDOW_MIN = 15

# Pitch zones: x 0..100 attacking left→right for the team in possession, y 0..100 top→bottom.
# Thirds: defensive (<33), middle (33-66), final (>66). Lanes: left (<33), centre, right (>66).
EVENT_TYPES = (
    "pass",
    "cross",
    "shot",
    "duel",
    "pressure",
    "tackle",
    "interception",
    "clearance",
    "corner",
    "foul",
    "sprint",
    "carry",
    "goal",
    "card",
    "substitution",
)


@dataclass
class Event:
    minute: float
    team: str  # club_id
    type: str  # one of EVENT_TYPES
    player: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    success: Optional[bool] = None
    xg: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def lane(self) -> str:
        if self.y is None:
            return "centre"
        return "left" if self.y < 33 else ("right" if self.y > 66 else "centre")

    @property
    def third(self) -> str:
        if self.x is None:
            return "middle"
        return "defensive" if self.x < 33 else ("final" if self.x > 66 else "middle")

    def to_dict(self) -> dict[str, Any]:
        return {
            "minute": self.minute,
            "team": self.team,
            "type": self.type,
            "player": self.player,
            "x": self.x,
            "y": self.y,
            "success": self.success,
            "xg": self.xg,
            **({"meta": self.meta} if self.meta else {}),
        }


@dataclass
class WindowStats:
    passes: int = 0
    passes_ok: int = 0
    final_third_passes: int = 0
    shots: int = 0
    xg: float = 0.0
    crosses_by_lane: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    attacks_by_lane: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    def_actions: int = 0  # tackles + interceptions + pressures + clearances
    high_turnovers: int = 0  # opponent lost ball in their defensive third under our pressure
    corners: int = 0
    aerials: int = 0
    aerials_won: int = 0
    sprints: int = 0

    @property
    def pass_pct(self) -> Optional[float]:
        return round(self.passes_ok / self.passes * 100, 1) if self.passes else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passes": self.passes,
            "pass_pct": self.pass_pct,
            "final_third_passes": self.final_third_passes,
            "shots": self.shots,
            "xg": round(self.xg, 2),
            "crosses_by_lane": dict(self.crosses_by_lane),
            "attacks_by_lane": dict(self.attacks_by_lane),
            "def_actions": self.def_actions,
            "high_turnovers": self.high_turnovers,
            "corners": self.corners,
            "aerials": self.aerials,
            "aerials_won": self.aerials_won,
            "sprints": self.sprints,
        }


@dataclass
class PlayerLive:
    name: str
    team: str
    position: str
    on_pitch: bool = True
    minutes: float = 0.0
    entered_at: float = 0.0
    touches: int = 0
    passes: int = 0
    passes_ok: int = 0
    duels: int = 0
    duels_won: int = 0
    sprints_by_window: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    touches_by_window: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    xg: float = 0.0
    cards: int = 0

    def fatigue(self, minute: float) -> float:
        """0..1 — minutes-driven load, corrected by sprint decay vs the player's own first window."""
        played = max(0.0, minute - self.entered_at)
        base = min(1.0, played / 95.0)
        wins = sorted(self.sprints_by_window)
        if len(wins) >= 2 and self.sprints_by_window[wins[0]] >= 4:
            first, last = self.sprints_by_window[wins[0]], self.sprints_by_window[wins[-1]]
            decay = max(0.0, 1 - last / first)  # 0 no decay .. 1 total collapse
            base = min(1.0, base * 0.7 + decay * 0.5)
        return round(base, 2)

    def to_dict(self, minute: float) -> dict[str, Any]:
        return {
            "name": self.name,
            "team": self.team,
            "position": self.position,
            "on_pitch": self.on_pitch,
            "minutes": round(
                max(0.0, (minute if self.on_pitch else self.minutes) - self.entered_at), 1
            ),
            "touches": self.touches,
            "pass_pct": round(self.passes_ok / self.passes * 100) if self.passes else None,
            "duels": self.duels,
            "duels_won": self.duels_won,
            "xg": round(self.xg, 2),
            "cards": self.cards,
            "fatigue": self.fatigue(minute) if self.on_pitch else None,
            "sprints_by_window": dict(self.sprints_by_window),
        }


@dataclass
class MatchState:
    home: str
    away: str
    minute: float = 0.0
    score: dict[str, int] = field(default_factory=dict)
    windows: dict[str, dict[int, WindowStats]] = field(
        default_factory=dict
    )  # team -> window idx -> stats
    players: dict[str, PlayerLive] = field(default_factory=dict)  # key "team:name"
    log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for t in (self.home, self.away):
            self.score.setdefault(t, 0)
            self.windows.setdefault(t, defaultdict(WindowStats))

    @staticmethod
    def window_of(minute: float) -> int:
        return int(minute // WINDOW_MIN)

    def opponent(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def window(self, team: str, idx: Optional[int] = None) -> WindowStats:
        idx = self.window_of(self.minute) if idx is None else idx
        return self.windows[team][idx]

    def player(self, team: str, name: str, position: str = "?") -> PlayerLive:
        key = f"{team}:{name}"
        if key not in self.players:
            self.players[key] = PlayerLive(
                name=name, team=team, position=position, entered_at=self.minute
            )
        return self.players[key]

    def on_pitch(self, team: str) -> list[PlayerLive]:
        return [p for p in self.players.values() if p.team == team and p.on_pitch]

    # ------------------------------------------------------------------ apply
    def apply(self, ev: Event) -> None:
        self.minute = max(self.minute, ev.minute)
        w = self.window(ev.team, self.window_of(ev.minute))
        opp_w = self.window(self.opponent(ev.team), self.window_of(ev.minute))
        widx = self.window_of(ev.minute)
        pl = self.player(ev.team, ev.player) if ev.player else None
        if pl and ev.type not in ("substitution", "card"):
            pl.touches += 1
            pl.touches_by_window[widx] += 1
        t = ev.type
        if t == "pass":
            w.passes += 1
            if ev.success:
                w.passes_ok += 1
            if ev.third == "final":
                w.final_third_passes += 1
                w.attacks_by_lane[ev.lane] += 1
            if pl:
                pl.passes += 1
                pl.passes_ok += 1 if ev.success else 0
        elif t == "carry":
            if ev.third == "final":
                w.attacks_by_lane[ev.lane] += 1
        elif t == "cross":
            w.crosses_by_lane[ev.lane] += 1
            w.attacks_by_lane[ev.lane] += 1
        elif t == "shot":
            w.shots += 1
            w.xg += ev.xg
            if pl:
                pl.xg += ev.xg
            if ev.lane:
                w.attacks_by_lane[ev.lane] += 1
        elif t == "goal":
            self.score[ev.team] += 1
            w.shots += 1
            w.xg += ev.xg
            if pl:
                pl.xg += ev.xg
            self.log.append(
                {"minute": ev.minute, "type": "goal", "team": ev.team, "player": ev.player}
            )
        elif t in ("tackle", "interception", "clearance", "pressure"):
            w.def_actions += 1
            if t in ("tackle", "interception") and ev.x is not None and ev.x > 66:
                w.high_turnovers += 1
        elif t == "duel":
            if pl:
                pl.duels += 1
                pl.duels_won += 1 if ev.success else 0
            if ev.meta.get("aerial"):
                w.aerials += 1
                w.aerials_won += 1 if ev.success else 0
                opp_w.aerials += 1
                opp_w.aerials_won += 0 if ev.success else 1
        elif t == "corner":
            w.corners += 1
        elif t == "sprint":
            w.sprints += 1
            if pl:
                pl.sprints_by_window[widx] += 1
        elif t == "card":
            if pl:
                pl.cards += 1
            self.log.append(
                {
                    "minute": ev.minute,
                    "type": "card",
                    "team": ev.team,
                    "player": ev.player,
                    "card": ev.meta.get("card", "yellow"),
                }
            )
        elif t == "substitution":
            off, on, pos = ev.meta.get("off"), ev.meta.get("on"), ev.meta.get("position", "?")
            if off:
                p_off = self.player(ev.team, off)
                p_off.on_pitch = False
                p_off.minutes = ev.minute
            if on:
                p_on = self.player(ev.team, on, pos)
                p_on.on_pitch = True
                p_on.entered_at = ev.minute
                if pos != "?":
                    p_on.position = pos
            self.log.append(
                {"minute": ev.minute, "type": "substitution", "team": ev.team, "off": off, "on": on}
            )

    # --------------------------------------------------------------- metrics
    def ppda(self, team: str, idx: Optional[int] = None) -> Optional[float]:
        """Passes allowed per defensive action: opponent passes / our defensive actions (lower = more intense press)."""
        idx = self.window_of(self.minute) if idx is None else idx
        opp = self.window(self.opponent(team), idx)
        ours = self.window(team, idx)
        return round(opp.passes / ours.def_actions, 2) if ours.def_actions else None

    def possession(self, team: str, idx: Optional[int] = None) -> Optional[float]:
        idx = self.window_of(self.minute) if idx is None else idx
        a, b = self.window(team, idx).passes, self.window(self.opponent(team), idx).passes
        return round(a / (a + b) * 100, 1) if a + b else None

    def field_tilt(self, team: str, idx: Optional[int] = None) -> Optional[float]:
        idx = self.window_of(self.minute) if idx is None else idx
        a, b = (
            self.window(team, idx).final_third_passes,
            self.window(self.opponent(team), idx).final_third_passes,
        )
        return round(a / (a + b) * 100, 1) if a + b else None

    def snapshot(self) -> dict[str, Any]:
        widx = self.window_of(self.minute)
        out: dict[str, Any] = {
            "minute": round(self.minute, 1),
            "score": dict(self.score),
            "window": widx,
            "teams": {},
        }
        for t in (self.home, self.away):
            out["teams"][t] = {
                "possession": self.possession(t),
                "field_tilt": self.field_tilt(t),
                "ppda": self.ppda(t),
                "xg_total": round(sum(w.xg for w in self.windows[t].values()), 2),
                "shots_total": sum(w.shots for w in self.windows[t].values()),
                "windows": {i: w.to_dict() for i, w in sorted(self.windows[t].items())},
                "players": [p.to_dict(self.minute) for p in self.players.values() if p.team == t],
            }
        out["log"] = self.log[-12:]
        return out
