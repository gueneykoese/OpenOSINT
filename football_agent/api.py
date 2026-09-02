"""FastAPI backend.  Run:  uvicorn football_agent.api:app --reload"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from . import __version__
from .commission import quote
from .llm import narrate
from .loader import dataset_status, load_clubs, load_players, validate_dataset
from .matching import MatchEngine

app = FastAPI(
    title="football_agent — AI-assisted player agency (UCL 2026/27 pilot)",
    version=__version__,
    description=(
        "Explainable player↔club matching. Scores are deterministic and every dimension "
        "carries a justification; Claude is used only to narrate and stress-test, never to score."
    ),
)


@lru_cache(maxsize=1)
def engine() -> MatchEngine:
    include_demo = os.environ.get("FOOTBALL_AGENT_INCLUDE_DEMO", "0") == "1"
    return MatchEngine(load_clubs(), load_players(include_demo=include_demo))


@app.get("/health")
def health() -> dict:
    e = engine()
    return {
        "status": "ok",
        "clubs": len(e.clubs),
        "players": len(e.players),
        "version": __version__,
    }


@app.get("/dataset/validate")
def dataset_validate() -> dict:
    problems = validate_dataset()
    return {"ok": not problems, "problems": problems}


@app.get("/dataset/status")
def dataset_status_endpoint() -> dict:
    return dataset_status()


@app.get("/clubs")
def clubs(pot: Optional[int] = None, country: Optional[str] = None) -> list[dict]:
    out = []
    for c in engine().clubs.values():
        if pot and c.pot != pot:
            continue
        if country and (c.country or "").upper() != country.upper():
            continue
        out.append(
            {
                "club_id": c.club_id,
                "name": c.name,
                "country": c.country,
                "league": c.league,
                "pot": c.pot,
                "coach": c.coach_name,
                "formation": c.formation,
                "league_position_2025_26": c.last_season.get("league_position"),
                "needs": [n.position for n in c.positional_needs],
                "confidence": c.confidence,
            }
        )
    return out


@app.get("/clubs/{club_id}")
def club(club_id: str) -> dict:
    c = engine().clubs.get(club_id)
    if not c:
        raise HTTPException(404, f"unknown club {club_id}")
    return c.raw


@app.get("/clubs/{club_id}/recommendations")
def club_recommendations(club_id: str, per_need: int = Query(3, ge=1, le=10)) -> dict:
    e = engine()
    if club_id not in e.clubs:
        raise HTTPException(404, f"unknown club {club_id}")
    recs = e.club_recommendations(club_id, per_need=per_need)
    return {pos: [r.to_dict() for r in rs] for pos, rs in recs.items()}


@app.get("/clubs/{club_id}/candidates")
def club_candidates(
    club_id: str,
    position: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    min_total: float = 0.0,
) -> list[dict]:
    e = engine()
    if club_id not in e.clubs:
        raise HTTPException(404, f"unknown club {club_id}")
    return [
        r.to_dict()
        for r in e.rank_players_for_club(
            club_id, position=position, limit=limit, min_total=min_total
        )
    ]


@app.get("/players")
def players(position: Optional[str] = None, max_fee: Optional[float] = None) -> list[dict]:
    out = []
    for p in engine().players.values():
        if position and position.upper() not in p.all_positions:
            continue
        if max_fee is not None and (p.estimated_fee_eur_m or 0) > max_fee:
            continue
        out.append(
            {
                "player_id": p.player_id,
                "name": p.name,
                "age": p.age,
                "position": p.position,
                "current_club": p.current_club,
                "contract_until": p.contract_until,
                "estimated_fee_eur_m": p.estimated_fee_eur_m,
                "availability": p.availability,
                "confidence": p.confidence,
            }
        )
    return out


@app.get("/players/{player_id}")
def player(player_id: str) -> dict:
    p = engine().players.get(player_id)
    if not p:
        raise HTTPException(404, f"unknown player {player_id}")
    return p.raw


@app.get("/players/{player_id}/clubs")
def player_clubs(
    player_id: str, limit: int = Query(10, ge=1, le=36), min_total: float = 0.0
) -> list[dict]:
    e = engine()
    if player_id not in e.players:
        raise HTTPException(404, f"unknown player {player_id}")
    return [
        r.to_dict() for r in e.rank_clubs_for_player(player_id, limit=limit, min_total=min_total)
    ]


@app.get("/match/{player_id}/{club_id}")
def match(player_id: str, club_id: str, narrative: bool = False) -> dict:
    e = engine()
    p, c = e.players.get(player_id), e.clubs.get(club_id)
    if not p or not c:
        raise HTTPException(404, "unknown player or club")
    r = e.score(p, c)
    out = r.to_dict()
    if narrative:
        out["narrative"] = narrate(r, p, c)
    return out


@app.get("/matches/mutual")
def mutual(top_n_clubs: int = 5, top_n_players: int = 5, min_total: float = 60.0) -> list[dict]:
    return [r.to_dict() for r in engine().mutual_matches(top_n_clubs, top_n_players, min_total)]


@app.get("/commission")
def commission(
    transfer_fee_eur_m: float,
    gross_annual_salary_eur_m: float,
    contract_years: int = 4,
    our_rate: float = 0.02,
    market_rate: float = 0.10,
) -> dict:
    try:
        return quote(
            transfer_fee_eur_m, gross_annual_salary_eur_m, contract_years, our_rate, market_rate
        ).to_dict()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
