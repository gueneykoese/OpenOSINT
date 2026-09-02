"""The matching engine: explainable, deterministic, bidirectional."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from ..models import Club, DimensionScore, MatchResult, Player
from . import dimensions as dim
from .weights import DEFAULT_WEIGHTS, Weights

_LABELS = {
    "need_fit": "Positional need",
    "statistical_fit": "Statistical fit",
    "tactical_fit": "Tactical / system fit",
    "financial": "Financial feasibility",
    "age_contract": "Age & contract",
    "injury_risk": "Injury risk",
    "mental_chemistry": "Mentality & chemistry",
    "cultural_fit": "Cultural adaptation",
}


def verdict_for(total: float) -> str:
    if total >= 78:
        return "strong match"
    if total >= 66:
        return "good match"
    if total >= 54:
        return "possible"
    if total >= 40:
        return "weak"
    return "no fit"


@dataclass
class MatchEngine:
    clubs: dict[str, Club]
    players: dict[str, Player]
    weights: Weights = field(default_factory=lambda: DEFAULT_WEIGHTS)

    def __post_init__(self) -> None:
        self.weights.validate()

    # ------------------------------------------------------------------ core
    def score(self, player: Player, club: Club) -> MatchResult:
        pos, need, how = dim.resolve_position(player, club)
        w = self.weights
        raw = {
            "need_fit": dim.need_fit(player, club, pos, need, how),
            "statistical_fit": dim.statistical_fit(player, club, pos),
            "tactical_fit": dim.tactical_fit(player, club),
            "financial": dim.financial(player, club, need),
            "age_contract": dim.age_contract(player, club),
            "injury_risk": dim.injury_risk(player, club),
            "mental_chemistry": dim.mental_chemistry(player, club),
            "cultural_fit": dim.cultural_fit(player, club),
        }
        dims = [
            DimensionScore(
                key=k,
                label=_LABELS[k],
                score=s,
                weight=getattr(w, k),
                explanation=e,
                data_coverage=c,
            )
            for k, (s, e, c) in raw.items()
        ]
        total = round(sum(d.weighted for d in dims), 1)
        red, review = dim.collect_flags(player, club, pos)
        coverage = sum(d.data_coverage * d.weight for d in dims)
        if coverage >= 0.75 and player.confidence != "low" and club.confidence != "low":
            confidence = "high"
        elif coverage >= 0.5:
            confidence = "medium"
        else:
            confidence = "low"
        if player.confidence == "synthetic" or club.confidence == "synthetic":
            confidence = "demo"
            review.append(
                "FICTIONAL demo profile involved — this result only demonstrates the engine."
            )
        top = sorted(dims, key=lambda d: d.weighted, reverse=True)[:2]
        weakest = min(dims, key=lambda d: d.score)
        summary = (
            f"{player.name} → {club.short_name} at {pos}: {verdict_for(total)} ({total}/100). "
            f"Driven by {top[0].label.lower()} and {top[1].label.lower()}; weakest area is "
            f"{weakest.label.lower()} ({weakest.score:.0f})."
        )
        return MatchResult(
            player_id=player.player_id,
            player_name=player.name,
            club_id=club.club_id,
            club_name=club.short_name,
            position=pos,
            total=total,
            verdict=verdict_for(total),
            dimensions=dims,
            red_flags=red,
            human_review=review,
            confidence=confidence,
            summary=summary,
        )

    # ------------------------------------------------------------- rankings
    def rank_players_for_club(
        self,
        club_id: str,
        position: Optional[str] = None,
        limit: int = 10,
        players: Optional[Iterable[Player]] = None,
        min_total: float = 0.0,
    ) -> list[MatchResult]:
        club = self.clubs[club_id]
        pool = list(players) if players is not None else list(self.players.values())
        if position:
            position = position.upper()
            pool = [p for p in pool if position in p.all_positions]
        # never recommend a club its own player
        pool = [
            p
            for p in pool
            if (p.current_club or "").lower() not in {club.name.lower(), club.short_name.lower()}
        ]
        results = [self.score(p, club) for p in pool]
        results = [r for r in results if r.total >= min_total]
        results.sort(key=lambda r: r.total, reverse=True)
        return results[:limit]

    def rank_clubs_for_player(
        self, player_id: str, limit: int = 10, min_total: float = 0.0
    ) -> list[MatchResult]:
        player = self.players[player_id]
        results = [
            self.score(player, c)
            for c in self.clubs.values()
            if (player.current_club or "").lower() not in {c.name.lower(), c.short_name.lower()}
        ]
        results = [r for r in results if r.total >= min_total]
        results.sort(key=lambda r: r.total, reverse=True)
        return results[:limit]

    def mutual_matches(
        self, top_n_clubs: int = 5, top_n_players: int = 5, min_total: float = 60.0
    ) -> list[MatchResult]:
        """A match is *mutual* when the club is in the player's top-N clubs AND the
        player is in the club's top-N players for that position. This is the list an
        agent should actually pick up the phone for."""
        club_tops: dict[str, set[str]] = {}
        for cid in self.clubs:
            club_tops[cid] = {
                r.player_id
                for r in self.rank_players_for_club(cid, limit=top_n_players, min_total=min_total)
            }
        out: list[MatchResult] = []
        for pid in self.players:
            for r in self.rank_clubs_for_player(pid, limit=top_n_clubs, min_total=min_total):
                if pid in club_tops.get(r.club_id, set()):
                    out.append(r)
        out.sort(key=lambda r: r.total, reverse=True)
        return out

    def club_recommendations(self, club_id: str, per_need: int = 3) -> dict[str, list[MatchResult]]:
        """For each stated positional need, the best candidates from the pool."""
        club = self.clubs[club_id]
        out: dict[str, list[MatchResult]] = {}
        for need in club.positional_needs:
            out[need.position] = self.rank_players_for_club(
                club_id, position=need.position, limit=per_need
            )
        return out
