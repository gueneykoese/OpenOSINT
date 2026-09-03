"""Cultural-adaptation model based on Geert Hofstede's national culture dimensions.

Hofstede's framework started with four dimensions (PDI, IDV, MAS, UAI, 1980), added
Long-Term Orientation as the fifth (1991) and Indulgence vs. Restraint as the sixth
(2010). The user asked for the classic **5-D** model, so the default distance uses
PDI, IDV, MAS, UAI and LTO; IVR is loaded and can be switched on via
``HOFSTEDE_DIMENSIONS``.

Distance metric: the Kogut & Singh (1988) composite index, the standard in the
international-business literature::

    CD(a, b) = (1/n) * sum_i ( (I_ia - I_ib)^2 / V_i )

where V_i is the variance of dimension i across all countries in the dataset. It is
symmetric and dimensionless; in practice values fall roughly between 0 (identical)
and ~6 (maximally different). We convert it to a 0-100 adaptation score.

A player's *familiar cultures* are the countries of nationality plus the country of
the league they currently play in (they have already adapted there). The distance
that matters is the smallest one from any familiar culture to the destination club's
country.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

DATA_FILE = Path(__file__).parent / "data" / "hofstede.json"

# Classic 5-D model by default (Hofstede 1991). Add "ivr" for the 2010 6-D version.
HOFSTEDE_DIMENSIONS: tuple[str, ...] = ("pdi", "idv", "mas", "uai", "lto")

DIMENSION_LABELS = {
    "pdi": "Power Distance",
    "idv": "Individualism",
    "mas": "Masculinity",
    "uai": "Uncertainty Avoidance",
    "lto": "Long-Term Orientation",
    "ivr": "Indulgence",
}

# How to read a gap in football terms. (higher_in_player_culture, higher_in_club_culture)
_INTERPRET = {
    "pdi": (
        "player's familiar culture is more hierarchical than the club's — expect a flatter coach-player dynamic and more expectation of self-management",
        "club culture is more hierarchical than the player's — expect a more top-down coach and less room for open disagreement",
    ),
    "idv": (
        "player comes from a more individualist culture — the club environment will be more group-oriented (collective rituals, loyalty expectations)",
        "player comes from a more collectivist culture — the club environment is more individualist (self-promotion, less automatic group support)",
    ),
    "mas": (
        "player's familiar culture is more competition/achievement-driven than the club's — dressing-room tone may feel less confrontational",
        "club culture is more competition/achievement-driven — harsher performance culture and media tone than the player is used to",
    ),
    "uai": (
        "player's familiar culture tolerates ambiguity less than the club's — looser structures and improvisation may feel unsettling",
        "club culture avoids uncertainty more — expect more rules, fixed routines and formal structure than the player is used to",
    ),
    "lto": (
        "player's familiar culture is more long-term oriented than the club's — the club/market will prize immediate results more",
        "club culture is more long-term oriented — patience and development pathways matter more than quick wins",
    ),
    "ivr": (
        "player's familiar culture is more indulgent — the club environment is more restrained (stricter social norms, less leisure emphasis)",
        "club culture is more indulgent — looser social norms than the player is used to",
    ),
}

# Countries the football world treats separately but Hofstede scores as one unit.
_ALIASES = {"SCO": "GBR", "WAL": "GBR", "NIR": "GBR", "ENG": "GBR", "GBR": "GBR"}

_LEAGUE_COUNTRY = {
    "premier league": "ENG",
    "la liga": "ESP",
    "laliga": "ESP",
    "bundesliga": "GER",
    "serie a": "ITA",
    "ligue 1": "FRA",
    "eredivisie": "NED",
    "liga portugal": "POR",
    "primeira liga": "POR",
    "süper lig": "TUR",
    "super lig": "TUR",
    "pro league": "BEL",
    "jupiler": "BEL",
    "eliteserien": "NOR",
    "allsvenskan": "SWE",
    "superliga": "DEN",
    "fortuna liga": "CZE",
    "czech": "CZE",
    "niké liga": "SVK",
    "slovak": "SVK",
    "super league greece": "GRE",
    "super league 1": "GRE",
    "austrian": "AUT",
    "premyer": "AZE",
    "ukrainian": "UKR",
    "championship": "ENG",
    "scottish": "SCO",
    "swiss super league": "SUI",
    "brasileir": "BRA",
    "primera división argentina": "ARG",
    "liga profesional": "ARG",
    "mls": "USA",
    "liga mx": "MEX",
    "j1": "JPN",
    "k league": "KOR",
    "saudi": "SAU",
}


def league_country(league: Optional[str]) -> Optional[str]:
    lg = (league or "").lower()
    for k, c in _LEAGUE_COUNTRY.items():
        if k in lg:
            return c
    return None


@dataclass
class CountryScores:
    code: str
    name: str
    scores: dict[str, Optional[float]]
    proxy: Optional[str] = None


@dataclass
class HofstedeModel:
    countries: dict[str, CountryScores]
    dimensions: tuple[str, ...] = HOFSTEDE_DIMENSIONS
    sources: list[str] = field(default_factory=list)
    note: str = ""
    _variance: dict[str, float] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for d in self.dimensions:
            vals = [c.scores.get(d) for c in self.countries.values()]
            vals = [float(v) for v in vals if isinstance(v, (int, float))]
            if len(vals) >= 2:
                mean = sum(vals) / len(vals)
                self._variance[d] = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)

    # ------------------------------------------------------------------ lookup
    def resolve(self, code: Optional[str]) -> Optional[CountryScores]:
        if not code:
            return None
        code = _ALIASES.get(code.upper(), code.upper())
        c = self.countries.get(code)
        if c is None:
            return None
        core = ("pdi", "idv", "mas", "uai")
        if all(c.scores.get(d) is None for d in core) and c.proxy:
            p = self.countries.get(c.proxy.upper())
            if p is not None:
                return CountryScores(
                    code=c.code, name=f"{c.name} (proxy: {p.name})", scores=p.scores, proxy=c.proxy
                )
        return c

    def has_data(self, code: Optional[str]) -> bool:
        c = self.resolve(code)
        return bool(c) and any(c.scores.get(d) is not None for d in self.dimensions)

    # ---------------------------------------------------------------- distance
    def distance(self, a: str, b: str) -> Optional[float]:
        """Kogut-Singh cultural distance between two countries (None if no data)."""
        ca, cb = self.resolve(a), self.resolve(b)
        if not ca or not cb:
            return None
        terms = []
        for d in self.dimensions:
            va, vb, var = ca.scores.get(d), cb.scores.get(d), self._variance.get(d)
            if va is None or vb is None or not var:
                continue
            terms.append((float(va) - float(vb)) ** 2 / var)
        if not terms:
            return None
        return round(sum(terms) / len(terms), 3)

    def gaps(self, a: str, b: str) -> list[tuple[str, float, str]]:
        """Per-dimension (dimension, signed gap a-b, football-language interpretation), largest first."""
        ca, cb = self.resolve(a), self.resolve(b)
        if not ca or not cb:
            return []
        out = []
        for d in self.dimensions:
            va, vb = ca.scores.get(d), cb.scores.get(d)
            if va is None or vb is None:
                continue
            gap = float(va) - float(vb)
            interp = _INTERPRET[d][0] if gap > 0 else _INTERPRET[d][1]
            out.append((d, round(gap, 1), interp))
        out.sort(key=lambda t: abs(t[1]), reverse=True)
        return out

    @staticmethod
    def distance_to_score(cd: float) -> float:
        """0 distance -> 100; ~1 -> 78; ~2 -> 56; >=4.3 -> 5 (floor)."""
        return max(5.0, min(100.0, 100.0 - 22.0 * cd))

    # ------------------------------------------------------------- player fit
    def adaptation(
        self, familiar: Iterable[str], destination: Optional[str]
    ) -> tuple[Optional[float], Optional[str], list[tuple[str, float, str]], Optional[float]]:
        """Best (smallest) distance from any familiar culture to the destination.

        Returns (distance, from_code, gaps, score)."""
        if not destination or not self.has_data(destination):
            return None, None, [], None
        best: tuple[Optional[float], Optional[str]] = (None, None)
        for code in familiar:
            cd = self.distance(code, destination)
            if cd is None:
                continue
            if best[0] is None or cd < best[0]:
                best = (cd, code)
        if best[0] is None:
            return None, None, [], None
        return best[0], best[1], self.gaps(best[1], destination), self.distance_to_score(best[0])


@lru_cache(maxsize=1)
def load_model(
    path: Path = DATA_FILE, dimensions: tuple[str, ...] = HOFSTEDE_DIMENSIONS
) -> HofstedeModel:
    if not path.exists():
        return HofstedeModel(countries={}, dimensions=dimensions, note="hofstede.json missing")
    with path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    countries = {
        code.upper(): CountryScores(
            code=code.upper(),
            name=v.get("name", code),
            scores={d: v.get(d) for d in DIMENSION_LABELS},
            proxy=v.get("proxy"),
        )
        for code, v in (raw.get("countries") or {}).items()
    }
    return HofstedeModel(
        countries=countries,
        dimensions=dimensions,
        sources=raw.get("sources") or [],
        note=raw.get("note") or "",
    )
