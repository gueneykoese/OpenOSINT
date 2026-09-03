"""Unit tests for the football_agent matching engine (synthetic fixtures — no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from football_agent.commission import quote
from football_agent.loader import (
    CLUBS_DIR,
    PLAYERS_DIR,
    load_clubs,
    load_players,
    validate_club,
    validate_dataset,
    validate_player,
)
from football_agent.matching import MatchEngine, Weights
from football_agent.matching.engine import verdict_for
from football_agent.models import Club, Player

CLUB = {
    "club_id": "test_fc",
    "name": "Test FC",
    "short_name": "Test",
    "country": "ESP",
    "league": "La Liga",
    "ucl_2026_27": {"pot": 2},
    "head_coach": {
        "name": "Coach",
        "preferred_formation": "4-3-3",
        "style_keywords": ["high press", "possession"],
    },
    "identity": {
        "playing_style": "High-pressing possession side.",
        "principles": ["youth pathway"],
        "club_character": "Demanding, intense media scrutiny.",
        "ownership": "members",
        "political_and_social_context": None,
        "languages": ["es", "en"],
        "wage_structure": "hierarchical",
        "transfer_policy": "under-25 resale value",
        "injury_management_reputation": None,
    },
    "last_season_2025_26": {"league_position": 3},
    "summer_2026_window": {},
    "squad": [
        {
            "name": "Old Striker",
            "position": "ST",
            "age": 33,
            "role": "starter",
            "stats_2025_26": {"minutes": 2700, "goals": 12, "assists": 3},
        },
        {
            "name": "Kid CB",
            "position": "CB",
            "age": 21,
            "role": "starter",
            "stats_2025_26": {"minutes": 2500},
        },
    ],
    "strengths": ["press"],
    "weaknesses": ["ageing striker"],
    "positional_needs": [
        {
            "position": "ST",
            "priority": "high",
            "profile": "pressing forward, 21-26, left-footed",
            "reason": "starter is 33",
            "budget_eur_m": 40,
            "wage_ceiling_eur_m_net": 5,
        }
    ],
    "position_benchmarks": {"ST": {"goals_p90": 0.5, "assists_p90": 0.15}},
    "sources": ["https://example.com"],
    "as_of": "2026-09-02",
    "data_quality": {"confidence": "high", "notes": ""},
}

PLAYER = {
    "player_id": "young_striker",
    "name": "Young Striker",
    "age": 23,
    "nationality": ["NED"],
    "position": "ST",
    "secondary_positions": ["LW"],
    "preferred_foot": "left",
    "current_club": "Selling FC",
    "current_club_league": "Eredivisie",
    "contract_until": 2027,
    "market_value_eur_m": 20,
    "estimated_fee_eur_m": 25,
    "wage_eur_m_net": 1.2,
    "availability": "open to move",
    "stats_2025_26": {"competition": "Eredivisie", "minutes": 2600, "goals": 19, "assists": 6},
    "style_profile": {
        "tags": ["pressing forward", "left-footed", "runs in behind"],
        "best_system": ["4-3-3 high press"],
        "weak_in": ["target man role"],
    },
    "mental_profile": {
        "leadership": 3,
        "coachability": 4,
        "resilience": 4,
        "discipline": 4,
        "notes": None,
    },
    "injury_history": [],
    "off_pitch": {"languages": ["nl", "en"], "public_statements": []},
    "sources": ["https://example.com"],
    "as_of": "2026-09-02",
    "data_quality": {"confidence": "medium", "notes": ""},
}


@pytest.fixture
def engine() -> MatchEngine:
    club = Club.from_dict(CLUB)
    player = Player.from_dict(PLAYER)
    return MatchEngine({club.club_id: club}, {player.player_id: player})


def test_synthetic_fixtures_pass_schema_validation():
    assert validate_club(CLUB) == []
    assert validate_player(PLAYER) == []


def test_strong_match_is_explainable(engine):
    r = engine.score(engine.players["young_striker"], engine.clubs["test_fc"])
    assert r.position == "ST"
    assert r.total >= 70, r.summary
    assert r.verdict in ("good match", "strong match")
    keys = {d.key for d in r.dimensions}
    assert keys == set(Weights().as_dict())
    assert all(d.explanation for d in r.dimensions)
    # deterministic
    assert engine.score(engine.players["young_striker"], engine.clubs["test_fc"]).total == r.total


def test_total_is_weighted_sum(engine):
    r = engine.score(engine.players["young_striker"], engine.clubs["test_fc"])
    assert r.total == pytest.approx(sum(d.weighted for d in r.dimensions), abs=0.11)


def test_missing_data_is_neutral_not_fatal():
    club = Club.from_dict(CLUB)
    bare = Player.from_dict({"player_id": "x", "name": "X", "position": "CM", "sources": []})
    r = MatchEngine({club.club_id: club}, {"x": bare}).score(bare, club)
    assert 0 <= r.total <= 100
    assert r.confidence == "low"


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        Weights(need_fit=0.5).validate()


def test_expensive_old_player_scores_lower(engine):
    club = engine.clubs["test_fc"]
    good = engine.players["young_striker"]
    bad = Player.from_dict(
        PLAYER
        | {
            "player_id": "vet",
            "age": 33,
            "estimated_fee_eur_m": 90,
            "wage_eur_m_net": 12,
            "contract_until": 2030,
            "preferred_foot": "right",
            "injury_history": [{"type": "ACL", "season": "2025/26", "days_out": 200}],
        }
    )
    assert engine.score(bad, club).total < engine.score(good, club).total - 15
    assert any("90+ days" in f for f in engine.score(bad, club).red_flags)


def test_verdict_bands():
    assert verdict_for(90) == "strong match"
    assert verdict_for(30) == "no fit"


def test_commission_math():
    q = quote(30, 5, 4)
    assert q.our_fee_eur_m == pytest.approx((30 + 20) * 0.02)
    assert q.market_fee_eur_m == pytest.approx((30 + 20) * 0.10)
    assert q.saving_eur_m == pytest.approx(4.0)
    with pytest.raises(ValueError):
        quote(30, 5, 0)


@pytest.mark.skipif(not any(CLUBS_DIR.glob("*.json")), reason="pilot dataset not present")
def test_pilot_dataset_is_valid():
    problems = validate_dataset()
    assert problems == [], "\n".join(problems)
    clubs, players = load_clubs(), load_players()
    assert len(clubs) == 36, f"expected the 36 league-phase clubs, got {len(clubs)}"
    assert len(players) >= 1
    e = MatchEngine(clubs, players)
    for c in clubs.values():
        recs = e.club_recommendations(c.club_id, per_need=2)
        for pos, rs in recs.items():
            for r in rs:
                assert 0 <= r.total <= 100
                assert r.position in (pos, *[])


@pytest.mark.skipif(not any(PLAYERS_DIR.glob("*.json")), reason="pilot dataset not present")
def test_every_pilot_record_has_sources():
    for path in list(CLUBS_DIR.glob("*.json")) + list(PLAYERS_DIR.glob("*.json")):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        assert d.get("sources"), path.name


def test_api_smoke(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from football_agent import api

    monkeypatch.setattr(api, "engine", lambda: engine)
    c = TestClient(api.app)
    assert c.get("/health").json()["clubs"] == 1
    assert c.get("/clubs/test_fc/recommendations").status_code == 200
    body = c.get("/match/young_striker/test_fc").json()
    assert body["verdict"] in ("good match", "strong match")
    assert c.get("/match/nobody/test_fc").status_code == 404
    assert (
        c.get(
            "/commission", params={"transfer_fee_eur_m": 10, "gross_annual_salary_eur_m": 2}
        ).json()["our_rate"]
        == 0.02
    )


def test_hofstede_distance_is_symmetric_and_zero_for_same_country():
    from football_agent.culture import CountryScores, HofstedeModel

    m = HofstedeModel(
        countries={
            "TUR": CountryScores(
                "TUR", "Turkey", {"pdi": 66, "idv": 37, "mas": 45, "uai": 85, "lto": 46, "ivr": 49}
            ),
            "GBR": CountryScores(
                "GBR", "UK", {"pdi": 35, "idv": 89, "mas": 66, "uai": 35, "lto": 51, "ivr": 69}
            ),
            "ESP": CountryScores(
                "ESP", "Spain", {"pdi": 57, "idv": 51, "mas": 42, "uai": 86, "lto": 48, "ivr": 44}
            ),
            "SEN": CountryScores(
                "SEN",
                "Senegal",
                {d: None for d in ("pdi", "idv", "mas", "uai", "lto", "ivr")},
                proxy="WAF",
            ),
        }
    )
    assert m.distance("TUR", "TUR") == 0.0
    assert m.distance("TUR", "ENG") == m.distance("GBR", "TUR")  # ENG aliases to GBR
    assert m.distance("TUR", "ESP") < m.distance(
        "TUR", "ENG"
    )  # Spain culturally closer to Turkey than UK
    assert m.distance("SEN", "ESP") is None  # proxy target missing -> no data, never a guess
    cd, frm, gaps, score = m.adaptation(["TUR", "ESP"], "GBR")
    assert frm == "ESP" and 0 < score < 100 and gaps[0][0] in ("idv", "uai", "pdi")
    assert m.distance_to_score(0) == 100 and m.distance_to_score(10) == 5
