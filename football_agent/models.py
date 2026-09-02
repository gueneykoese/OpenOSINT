"""Typed domain models. Everything is Optional-tolerant: the pilot dataset is
sourced from the public web and many fields are legitimately unknown."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

POSITIONS = ("GK", "CB", "LB", "RB", "DM", "CM", "AM", "LW", "RW", "ST")

# Positions that are close enough that a player can realistically cover both.
POSITION_NEIGHBOURS: dict[str, set[str]] = {
    "GK": set(),
    "CB": {"DM", "RB", "LB"},
    "LB": {"CB", "LW", "RB"},
    "RB": {"CB", "RW", "LB"},
    "DM": {"CM", "CB"},
    "CM": {"DM", "AM"},
    "AM": {"CM", "LW", "RW", "ST"},
    "LW": {"RW", "AM", "ST", "LB"},
    "RW": {"LW", "AM", "ST", "RB"},
    "ST": {"AM", "LW", "RW"},
}


def _get(d: dict[str, Any], *path: str, default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur or cur[key] is None:
            return default
        cur = cur[key]
    return cur


@dataclass
class SeasonStats:
    competition: Optional[str] = None
    apps: Optional[int] = None
    starts: Optional[int] = None
    minutes: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)  # xg, per-90s, etc.

    @classmethod
    def from_dict(cls, d: Optional[dict[str, Any]]) -> "SeasonStats":
        d = d or {}
        known = {"competition", "apps", "starts", "minutes", "goals", "assists"}
        return cls(
            competition=d.get("competition"),
            apps=d.get("apps"),
            starts=d.get("starts"),
            minutes=d.get("minutes"),
            goals=d.get("goals"),
            assists=d.get("assists"),
            extra={k: v for k, v in d.items() if k not in known},
        )

    def per90(self, value: Optional[int]) -> Optional[float]:
        if value is None or not self.minutes or self.minutes < 270:
            return None
        return round(value / self.minutes * 90, 3)

    @property
    def goals_p90(self) -> Optional[float]:
        return self.per90(self.goals)

    @property
    def assists_p90(self) -> Optional[float]:
        return self.per90(self.assists)

    @property
    def goal_contrib_p90(self) -> Optional[float]:
        if self.goals is None and self.assists is None:
            return None
        return self.per90((self.goals or 0) + (self.assists or 0))


@dataclass
class SquadPlayer:
    name: str
    position: str
    secondary_positions: list[str] = field(default_factory=list)
    age: Optional[int] = None
    nationality: Optional[str] = None
    contract_until: Optional[int] = None
    role: Optional[str] = None  # starter|rotation|backup|prospect
    stats: SeasonStats = field(default_factory=SeasonStats)
    injury_flag: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SquadPlayer":
        return cls(
            name=d.get("name", "?"),
            position=(d.get("position") or "?").upper(),
            secondary_positions=[p.upper() for p in d.get("secondary_positions") or []],
            age=d.get("age"),
            nationality=d.get("nationality"),
            contract_until=d.get("contract_until"),
            role=d.get("role"),
            stats=SeasonStats.from_dict(d.get("stats_2025_26")),
            injury_flag=d.get("injury_flag"),
        )


@dataclass
class PositionalNeed:
    position: str
    priority: str  # high|medium|low
    profile: str = ""
    reason: str = ""
    budget_eur_m: Optional[float] = None
    wage_ceiling_eur_m_net: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PositionalNeed":
        return cls(
            position=(d.get("position") or "?").upper(),
            priority=(d.get("priority") or "low").lower(),
            profile=d.get("profile") or "",
            reason=d.get("reason") or "",
            budget_eur_m=d.get("budget_eur_m"),
            wage_ceiling_eur_m_net=d.get("wage_ceiling_eur_m_net"),
        )


@dataclass
class Club:
    club_id: str
    name: str
    short_name: str
    country: Optional[str]
    league: Optional[str]
    pot: Optional[int]
    coach_name: Optional[str]
    formation: Optional[str]
    style_keywords: list[str]
    playing_style: str
    principles: list[str]
    club_character: str
    ownership: Optional[str]
    political_and_social_context: Optional[str]
    languages: list[str]
    wage_structure: Optional[str]
    transfer_policy: Optional[str]
    injury_management_reputation: Optional[str]
    last_season: dict[str, Any]
    summer_window: dict[str, Any]
    squad: list[SquadPlayer]
    strengths: list[str]
    weaknesses: list[str]
    positional_needs: list[PositionalNeed]
    position_benchmarks: dict[str, dict[str, Optional[float]]]
    ucl: dict[str, Any]
    sources: list[str]
    as_of: Optional[str]
    confidence: str
    data_notes: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Club":
        identity = d.get("identity") or {}
        coach = d.get("head_coach") or {}
        return cls(
            club_id=d["club_id"],
            name=d.get("name", d["club_id"]),
            short_name=d.get("short_name") or d.get("name", d["club_id"]),
            country=d.get("country"),
            league=d.get("league"),
            pot=_get(d, "ucl_2026_27", "pot"),
            coach_name=coach.get("name"),
            formation=coach.get("preferred_formation"),
            style_keywords=[s.lower() for s in coach.get("style_keywords") or []],
            playing_style=identity.get("playing_style") or "",
            principles=[p.lower() for p in identity.get("principles") or []],
            club_character=identity.get("club_character") or "",
            ownership=identity.get("ownership"),
            political_and_social_context=identity.get("political_and_social_context"),
            languages=[lang.lower() for lang in identity.get("languages") or []],
            wage_structure=identity.get("wage_structure"),
            transfer_policy=identity.get("transfer_policy"),
            injury_management_reputation=identity.get("injury_management_reputation"),
            last_season=d.get("last_season_2025_26") or {},
            summer_window=d.get("summer_2026_window") or {},
            squad=[SquadPlayer.from_dict(p) for p in d.get("squad") or []],
            strengths=d.get("strengths") or [],
            weaknesses=d.get("weaknesses") or [],
            positional_needs=[PositionalNeed.from_dict(n) for n in d.get("positional_needs") or []],
            position_benchmarks={
                k.upper(): (v or {}) for k, v in (d.get("position_benchmarks") or {}).items()
            },
            ucl=d.get("ucl_2026_27") or {},
            sources=d.get("sources") or [],
            as_of=d.get("as_of"),
            confidence=_get(d, "data_quality", "confidence", default="low"),
            data_notes=_get(d, "data_quality", "notes", default=""),
            raw=d,
        )

    # ---- derived helpers -------------------------------------------------
    def players_in(self, position: str) -> list[SquadPlayer]:
        position = position.upper()
        return [p for p in self.squad if p.position == position]

    def starters_in(self, position: str) -> list[SquadPlayer]:
        pl = self.players_in(position)
        starters = [p for p in pl if (p.role or "").lower() == "starter"]
        return starters or pl[:1]

    def need_for(self, position: str) -> Optional[PositionalNeed]:
        position = position.upper()
        for n in self.positional_needs:
            if n.position == position:
                return n
        return None

    def incumbent_goal_contrib_p90(self, position: str) -> Optional[float]:
        vals = [p.stats.goal_contrib_p90 for p in self.starters_in(position)]
        vals = [v for v in vals if v is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    def spending_tier(self) -> int:
        """1 (elite) .. 4 (small) — derived from UCL pot, a crude but sourced proxy."""
        return self.pot or 4


@dataclass
class Player:
    player_id: str
    name: str
    age: Optional[int]
    nationality: list[str]
    position: str
    secondary_positions: list[str]
    preferred_foot: Optional[str]
    height_cm: Optional[int]
    current_club: Optional[str]
    current_club_league: Optional[str]
    contract_until: Optional[int]
    market_value_eur_m: Optional[float]
    estimated_fee_eur_m: Optional[float]
    wage_eur_m_net: Optional[float]
    release_clause_eur_m: Optional[float]
    agent_status: Optional[str]
    availability: Optional[str]
    stats: SeasonStats
    style_tags: list[str]
    best_system: list[str]
    weak_in: list[str]
    mental: dict[str, Optional[int]]
    mental_notes: Optional[str]
    injury_history: list[dict[str, Any]]
    languages: list[str]
    public_statements: list[str]
    off_pitch_notes: Optional[str]
    sources: list[str]
    as_of: Optional[str]
    confidence: str
    data_notes: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Player":
        style = d.get("style_profile") or {}
        mental = d.get("mental_profile") or {}
        off = d.get("off_pitch") or {}
        nat = d.get("nationality")
        if isinstance(nat, str):
            nat = [nat]
        return cls(
            player_id=d["player_id"],
            name=d.get("name", d["player_id"]),
            age=d.get("age"),
            nationality=nat or [],
            position=(d.get("position") or "?").upper(),
            secondary_positions=[p.upper() for p in d.get("secondary_positions") or []],
            preferred_foot=d.get("preferred_foot"),
            height_cm=d.get("height_cm"),
            current_club=d.get("current_club"),
            current_club_league=d.get("current_club_league"),
            contract_until=d.get("contract_until"),
            market_value_eur_m=d.get("market_value_eur_m"),
            estimated_fee_eur_m=d.get("estimated_fee_eur_m"),
            wage_eur_m_net=d.get("wage_eur_m_net"),
            release_clause_eur_m=d.get("release_clause_eur_m"),
            agent_status=d.get("agent_status"),
            availability=d.get("availability"),
            stats=SeasonStats.from_dict(d.get("stats_2025_26")),
            style_tags=[t.lower() for t in style.get("tags") or []],
            best_system=[s.lower() for s in style.get("best_system") or []],
            weak_in=[w.lower() for w in style.get("weak_in") or []],
            mental={
                k: mental.get(k) for k in ("leadership", "coachability", "resilience", "discipline")
            },
            mental_notes=mental.get("notes"),
            injury_history=d.get("injury_history") or [],
            languages=[lang.lower() for lang in off.get("languages") or []],
            public_statements=off.get("public_statements") or [],
            off_pitch_notes=off.get("notes"),
            sources=d.get("sources") or [],
            as_of=d.get("as_of"),
            confidence=_get(d, "data_quality", "confidence", default="low"),
            data_notes=_get(d, "data_quality", "notes", default=""),
            raw=d,
        )

    @property
    def all_positions(self) -> list[str]:
        return [self.position, *self.secondary_positions]

    @property
    def total_days_injured(self) -> int:
        return sum(int(i.get("days_out") or 0) for i in self.injury_history)


@dataclass
class DimensionScore:
    key: str
    label: str
    score: float  # 0..100
    weight: float  # 0..1
    explanation: str
    data_coverage: float = 1.0  # 0..1, how much of the inputs were actually known

    @property
    def weighted(self) -> float:
        return round(self.score * self.weight, 2)


@dataclass
class MatchResult:
    player_id: str
    player_name: str
    club_id: str
    club_name: str
    position: str
    total: float
    verdict: str  # strong match | good match | possible | weak | no fit
    dimensions: list[DimensionScore]
    red_flags: list[str]
    human_review: list[str]
    confidence: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "club_id": self.club_id,
            "club_name": self.club_name,
            "position": self.position,
            "total": self.total,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "dimensions": [
                {
                    "key": d.key,
                    "label": d.label,
                    "score": round(d.score, 1),
                    "weight": d.weight,
                    "weighted": d.weighted,
                    "data_coverage": round(d.data_coverage, 2),
                    "explanation": d.explanation,
                }
                for d in self.dimensions
            ],
            "red_flags": self.red_flags,
            "human_review": self.human_review,
        }
