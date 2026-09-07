"""Deterministic SIMULATED event stream built from two club dossiers.

This is a demonstration feed, not real match data. It seeds each starting XI from
the club file, then generates minute-by-minute events with scripted tactical
phases so the analyzer has something to detect:

* phase A (0-30):  balanced, home side presses well
* phase B (30-55): away side overloads the home team's RIGHT flank (crosses, carries)
* phase C (55-80): home press collapses (PPDA rises), right-back's sprints decay,
                   striker isolated; away xG climbs
* phase D (80-95): late set-piece pressure against the home side

Production replaces this module with an adapter that maps a licensed live feed
(Opta/Stats Perform, StatsBomb, Second Spectrum) onto ``Event``.
"""

from __future__ import annotations

import random
from typing import Iterator, Optional

from ..models import Club, SquadPlayer
from .models import Event

_SLOTS = {"GK": 1, "CB": 2, "LB": 1, "RB": 1, "DM": 1, "CM": 2, "AM": 1, "LW": 1, "RW": 1, "ST": 1}


def starting_xi(club: Club) -> list[SquadPlayer]:
    """Starters from the dossier, filled to eleven by position quotas (deterministic)."""
    chosen: list[SquadPlayer] = []
    quota = dict(_SLOTS)
    for role in ("starter", "rotation", "backup", "prospect", None):
        for p in club.squad:
            if (
                (p.role or None) != role
                or p in chosen
                or quota.get(p.position, 0) <= 0
                or p.injury_flag
            ):
                continue
            chosen.append(p)
            quota[p.position] -= 1
        if len(chosen) >= 11:
            break
    for p in club.squad:  # fill any remaining slot regardless of quota
        if len(chosen) >= 11:
            break
        if p not in chosen and not p.injury_flag:
            chosen.append(p)
    return chosen[:11]


def bench(club: Club, xi: list[SquadPlayer]) -> list[SquadPlayer]:
    return [p for p in club.squad if p not in xi and not p.injury_flag][:9]


def _by_pos(xi: list[SquadPlayer], pos: str) -> Optional[SquadPlayer]:
    for p in xi:
        if p.position == pos:
            return p
    return None


def simulate_match(home: Club, away: Club, seed: int = 4, minutes: int = 95) -> Iterator[Event]:
    rng = random.Random(seed)
    hx, ax = starting_xi(home), starting_xi(away)
    h_rb, h_st, h_dm, h_lw = (
        _by_pos(hx, "RB"),
        _by_pos(hx, "ST"),
        _by_pos(hx, "DM"),
        _by_pos(hx, "LW"),
    )
    a_lw = _by_pos(ax, "LW")

    def pick(xi: list[SquadPlayer], weights: Optional[dict[str, float]] = None) -> SquadPlayer:
        if not weights:
            return rng.choice(xi)
        pool = [(p, weights.get(p.position, 1.0)) for p in xi]
        return rng.choices([p for p, _ in pool], [w for _, w in pool])[0]

    for m10 in range(minutes * 10):  # tenth-of-minute ticks
        minute = m10 / 10
        phase = "A" if minute < 30 else "B" if minute < 55 else "C" if minute < 80 else "D"
        home_poss = {"A": 0.55, "B": 0.48, "C": 0.42, "D": 0.45}[phase]
        team_is_home = rng.random() < home_poss
        team, xi, opp_xi = (home, hx, ax) if team_is_home else (away, ax, hx)
        opp = away if team_is_home else home

        # possession event: pass or carry
        if rng.random() < 0.9:
            third_x = rng.choices([20, 50, 80], [0.25, 0.45, 0.30])[0] + rng.uniform(-12, 12)
            # away overload of home RIGHT flank in phase B/C: away attacks down its LEFT (y small)
            if not team_is_home and phase in ("B", "C") and third_x > 60:
                y = rng.uniform(5, 30) if rng.random() < 0.65 else rng.uniform(30, 95)
                player = (
                    a_lw if a_lw and rng.random() < 0.5 else pick(xi, {"LW": 3, "LB": 2, "AM": 1.5})
                )
            else:
                y = rng.uniform(5, 95)
                player = pick(xi, {"CM": 2, "DM": 1.5, "CB": 1.4, "AM": 1.3})
            ok_p = {"A": 0.86, "B": 0.84, "C": 0.80, "D": 0.82}[phase] if team_is_home else 0.85
            if rng.random() < 0.15 and third_x > 60:
                yield Event(minute, team.club_id, "carry", player.name, third_x, y, True)
            else:
                yield Event(
                    minute, team.club_id, "pass", player.name, third_x, y, rng.random() < ok_p
                )
            # defensive reply from the opponent (press intensity)
            press = (
                {"A": 0.42, "B": 0.36, "C": 0.22, "D": 0.28}[phase]
                if team_is_home is False
                else 0.34
            )
            if rng.random() < press:
                dpl = pick(opp_xi, {"DM": 2.5, "CM": 2, "CB": 1.5, "RB": 1.2, "LB": 1.2})
                dtype = rng.choices(
                    ["pressure", "tackle", "interception", "clearance"], [0.5, 0.25, 0.15, 0.10]
                )[0]
                yield Event(
                    minute, opp.club_id, dtype, dpl.name, 100 - third_x, 100 - y, rng.random() < 0.6
                )
            # crosses & shots in final third
            if third_x > 66 and rng.random() < 0.22:
                if rng.random() < 0.45:
                    yield Event(
                        minute, team.club_id, "cross", player.name, 88, y, rng.random() < 0.3
                    )
                    if rng.random() < 0.5:
                        aerial_p = pick(opp_xi, {"CB": 3, "DM": 1})
                        won = rng.random() < (
                            {"A": 0.55, "B": 0.5, "C": 0.45, "D": 0.38}[phase]
                            if team_is_home is False
                            else 0.55
                        )
                        yield Event(
                            minute,
                            opp.club_id,
                            "duel",
                            aerial_p.name,
                            12,
                            100 - y,
                            won,
                            meta={"aerial": True},
                        )
                else:
                    shooter = pick(xi, {"ST": 4, "LW": 2, "RW": 2, "AM": 2})
                    xg = round(min(0.6, max(0.02, rng.gauss(0.11, 0.09))), 3)
                    if not team_is_home and phase == "C":
                        xg = round(min(0.7, xg * 1.4), 3)
                    goal = rng.random() < xg
                    yield Event(
                        minute,
                        team.club_id,
                        "goal" if goal else "shot",
                        shooter.name,
                        90,
                        y,
                        goal,
                        xg,
                    )
            if third_x > 66 and rng.random() < 0.06:
                yield Event(minute, team.club_id, "corner", None, 100, 0 if y < 50 else 100)
        # sprints (fatigue signal)
        if m10 % 3 == 0:
            for p in hx:
                base = 0.35 if p.position in ("RB", "LB", "LW", "RW", "ST") else 0.22
                if p is h_rb and phase in ("C", "D"):
                    base *= 0.35  # right-back fading
                if p is h_lw and phase == "D":
                    base *= 0.6
                if rng.random() < base:
                    yield Event(minute, home.club_id, "sprint", p.name)
            for p in ax:
                base = 0.35 if p.position in ("RB", "LB", "LW", "RW", "ST") else 0.22
                if rng.random() < base:
                    yield Event(minute, away.club_id, "sprint", p.name)
        # striker isolation: fewer home ST touches in phase C
        if h_st and phase != "C" and m10 % 7 == 0 and rng.random() < 0.5:
            yield Event(
                minute,
                home.club_id,
                "pass",
                h_st.name,
                78,
                rng.uniform(35, 65),
                rng.random() < 0.75,
            )
        # duels for midfield presence
        if m10 % 4 == 0 and h_dm and rng.random() < 0.3:
            yield Event(
                minute,
                home.club_id,
                "duel",
                h_dm.name,
                45,
                50,
                rng.random() < (0.6 if phase in ("A", "B") else 0.4),
            )
        # cards
        if m10 == 412 and h_rb:
            yield Event(minute, home.club_id, "card", h_rb.name, meta={"card": "yellow"})
