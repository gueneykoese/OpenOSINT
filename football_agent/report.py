"""Markdown report generation (club dossiers + recommendations)."""

from __future__ import annotations

from typing import Iterable

from .commission import quote
from .matching import MatchEngine
from .models import Club, MatchResult


def _fmt(v, suffix: str = "") -> str:
    return "n/a" if v is None else f"{v}{suffix}"


def club_dossier(club: Club, engine: MatchEngine, per_need: int = 3) -> str:
    ls = club.last_season
    lines = [f"# {club.name} — 2026/27 UCL dossier", ""]
    lines.append(
        f"**{club.league} ({club.country}) · Pot {club.pot} · Coach: {club.coach_name or 'n/a'}"
        f" · System: {club.formation or 'n/a'}**  "
    )
    lines.append(f"Data confidence: `{club.confidence}` · as of {club.as_of}")
    if club.data_notes:
        lines.append(f"> {club.data_notes}")
    lines += ["", "## 2025/26 in numbers", ""]
    lines.append("| Pos | Pts | W-D-L | GF | GA | Europe | Cup |")
    lines.append("|---|---|---|---|---|---|---|")
    lines.append(
        f"| {_fmt(ls.get('league_position'))} | {_fmt(ls.get('points'))} | "
        f"{_fmt(ls.get('won'))}-{_fmt(ls.get('drawn'))}-{_fmt(ls.get('lost'))} | "
        f"{_fmt(ls.get('goals_for'))} | {_fmt(ls.get('goals_against'))} | "
        f"{_fmt(ls.get('ucl_result'))} | {_fmt(ls.get('domestic_cup'))} |"
    )
    ts, ta = ls.get("top_scorer") or {}, ls.get("top_assister") or {}
    if ts or ta:
        lines.append("")
        lines.append(
            f"Top scorer: {ts.get('name', 'n/a')} ({_fmt(ts.get('goals'))}) · "
            f"Top assister: {ta.get('name', 'n/a')} ({_fmt(ta.get('assists'))})"
        )
    lines += ["", "## Identity", "", club.playing_style or "_n/a_", ""]
    if club.principles:
        lines.append("Principles: " + ", ".join(club.principles))
    if club.club_character:
        lines.append("")
        lines.append(f"Character: {club.club_character}")
    lines += ["", "## Strengths", ""] + [f"- {s}" for s in club.strengths]
    lines += ["", "## Weaknesses", ""] + [f"- {w}" for w in club.weaknesses]
    win = club.summer_window
    if win.get("arrivals") or win.get("departures"):
        lines += ["", "## Summer 2026 window", ""]
        for a in win.get("arrivals") or []:
            lines.append(
                f"- IN: {a.get('name')} ({a.get('position')}) from {a.get('from')} — €{_fmt(a.get('fee_eur_m'))}m"
            )
        for d in win.get("departures") or []:
            lines.append(
                f"- OUT: {d.get('name')} ({d.get('position')}) to {d.get('to')} — €{_fmt(d.get('fee_eur_m'))}m"
            )
    lines += [
        "",
        "## Current squad",
        "",
        "| Player | Pos | Age | Nat | Contract | Role | 25/26 Apps | G | A |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for p in club.squad:
        lines.append(
            f"| {p.name} | {p.position} | {_fmt(p.age)} | {_fmt(p.nationality)} | "
            f"{_fmt(p.contract_until)} | {_fmt(p.role)} | {_fmt(p.stats.apps)} | {_fmt(p.stats.goals)} | {_fmt(p.stats.assists)} |"
        )
    lines += ["", "## Positional needs & recommended targets", ""]
    recs = engine.club_recommendations(club.club_id, per_need=per_need)
    for need in club.positional_needs:
        lines.append(f"### {need.position} — {need.priority} priority")
        lines.append(f"Profile: {need.profile or 'n/a'}  ")
        lines.append(f"Why: {need.reason or 'n/a'}  ")
        lines.append(
            f"Budget: €{_fmt(need.budget_eur_m)}m · wage ceiling €{_fmt(need.wage_ceiling_eur_m_net)}m net"
        )
        lines.append("")
        for r in recs.get(need.position, []):
            lines.append(
                f"- **{r.player_name}** — {r.total}/100 ({r.verdict}, confidence {r.confidence})"
            )
            lines.append(f"  - {r.summary}")
            for f in r.red_flags:
                lines.append(f"  - ⚠ {f}")
        lines.append("")
    lines += ["## Sources", ""] + [f"- {s}" for s in club.sources]
    return "\n".join(lines) + "\n"


def match_table(results: Iterable[MatchResult]) -> str:
    rows = [
        "| Player | Club | Pos | Score | Verdict | Conf. | Flags |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        rows.append(
            f"| {r.player_name} | {r.club_name} | {r.position} | {r.total} | {r.verdict} | {r.confidence} | {len(r.red_flags)} |"
        )
    return "\n".join(rows) + "\n"


def commission_example(fee_eur_m: float, salary_eur_m: float, years: int = 4) -> str:
    q = quote(fee_eur_m, salary_eur_m, years)
    return (
        f"Transfer €{fee_eur_m}m + salary €{salary_eur_m}m × {years}y → "
        f"our 2% fee €{q.our_fee_eur_m}m vs market 10% €{q.market_fee_eur_m}m "
        f"(saving €{q.saving_eur_m}m for the parties)."
    )
