"""Build the self-contained HTML dashboard (data embedded, no server needed)."""

from __future__ import annotations

import json
from pathlib import Path

from ..commission import quote
from ..loader import DATA_DIR, dataset_status, load_clubs, load_players
from ..matching import MatchEngine

TEMPLATE = Path(__file__).parent / "template.html"


def export_data(include_demo: bool = False) -> dict:
    st = dataset_status()
    clubs, players = load_clubs(), load_players(include_demo=include_demo)
    e = MatchEngine(clubs, players)
    usable = st["clubs_usable_for_matching"]
    out: dict = {
        "status": st["clubs"],
        "usable": usable,
        "clubs": {},
        "players": {},
        "mutual": [r.to_dict() for r in e.mutual_matches(min_total=60)],
        "hofstede": json.loads((DATA_DIR / "hofstede.json").read_text(encoding="utf-8")),
        "commission": [quote(f, s, 4).to_dict() for f, s in ((35, 4), (18, 1.5), (70, 8))],
    }
    for cid, c in clubs.items():
        out["clubs"][cid] = {
            "usable": cid in usable,
            "name": c.name,
            "short": c.short_name,
            "country": c.country,
            "league": c.league,
            "pot": c.pot,
            "coach": c.coach_name,
            "formation": c.formation,
            "style": c.style_keywords,
            "confidence": c.confidence,
            "notes": c.data_notes,
            "playing_style": c.playing_style,
            "principles": c.principles,
            "character": c.club_character,
            "last": c.last_season,
            "strengths": c.strengths,
            "weaknesses": c.weaknesses,
            "window": c.summer_window,
            "opp_home": c.ucl.get("opponents_home"),
            "opp_away": c.ucl.get("opponents_away"),
            "squad": [
                {
                    "name": p.name,
                    "pos": p.position,
                    "age": p.age,
                    "nat": p.nationality,
                    "contract": p.contract_until,
                    "role": p.role,
                    "apps": p.stats.apps,
                    "g": p.stats.goals,
                    "a": p.stats.assists,
                    "inj": p.injury_flag,
                }
                for p in c.squad
            ],
            "needs": [
                {
                    "position": n.position,
                    "priority": n.priority,
                    "profile": n.profile,
                    "reason": n.reason,
                    "budget": n.budget_eur_m,
                    "wage": n.wage_ceiling_eur_m_net,
                }
                for n in c.positional_needs
            ],
            "recs": {
                pos: [r.to_dict() for r in rs]
                for pos, rs in e.club_recommendations(cid, per_need=3).items()
            },
            "sources": c.sources,
        }
    for pid, p in players.items():
        out["players"][pid] = {
            "name": p.name,
            "age": p.age,
            "pos": p.position,
            "sec": p.secondary_positions,
            "club": p.current_club,
            "league": p.current_club_league,
            "contract": p.contract_until,
            "fee": p.estimated_fee_eur_m,
            "wage": p.wage_eur_m_net,
            "avail": p.availability,
            "confidence": p.confidence,
            "nat": p.nationality,
            "notes": p.data_notes,
            "stats": {
                "comp": p.stats.competition,
                "apps": p.stats.apps,
                "min": p.stats.minutes,
                "g": p.stats.goals,
                "a": p.stats.assists,
            },
            "tags": p.style_tags,
            "mental": p.mental,
            "inj": p.injury_history,
            "langs": p.languages,
            "sources": p.sources,
            "clubs": [r.to_dict() for r in e.rank_clubs_for_player(pid, limit=6)],
        }
    return out


def build(out_path: Path, include_demo: bool = False) -> Path:
    data = json.dumps(export_data(include_demo), ensure_ascii=False, default=str).replace(
        "</", "<\\/"
    )
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
