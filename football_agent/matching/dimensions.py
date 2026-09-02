"""Individual scoring dimensions. Each returns (score 0..100, explanation, coverage 0..1).

Design rules
* Never crash on missing data: unknown inputs yield a neutral 50 and low coverage.
* Every score carries a one-sentence, human-readable justification.
* Soft/social dimensions can *flag* but cannot dominate (their weights are capped
  in weights.py, and political/social context is routed to `human_review`,
  never scored numerically)."""

from __future__ import annotations

import re
from typing import Optional

from ..models import POSITION_NEIGHBOURS, Club, Player, PositionalNeed

Score = tuple[float, str, float]

_PRIORITY_SCORE = {"high": 100.0, "medium": 72.0, "low": 45.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def resolve_position(player: Player, club: Club) -> tuple[str, Optional[PositionalNeed], str]:
    """Pick the position we evaluate the player at for this club.

    Preference: a club need matching the primary position > need matching a secondary
    position > primary position without a stated need."""
    for pos in player.all_positions:
        need = club.need_for(pos)
        if need:
            how = "primary" if pos == player.position else "secondary"
            return pos, need, how
    return player.position, None, "primary"


# --------------------------------------------------------------------------- need
_AGE_RANGE = re.compile(r"(\d{2})\s*[-–]\s*(\d{2})")
_UNDER = re.compile(r"(?:u|under)\s*-?\s*(\d{2})", re.I)


def need_fit(
    player: Player, club: Club, pos: str, need: Optional[PositionalNeed], how: str
) -> Score:
    if need is None:
        # No explicit gap. Is the position at least thin (few players / ageing)?
        incumbents = club.players_in(pos)
        neighbours = POSITION_NEIGHBOURS.get(pos, set())
        neighbour_need = next((n for n in club.positional_needs if n.position in neighbours), None)
        if neighbour_need:
            return (
                35.0,
                (
                    f"{club.short_name} has no stated need at {pos}, but wants a {neighbour_need.position} "
                    f"({neighbour_need.priority}) — adjacent role, partial fit."
                ),
                0.8,
            )
        if len(incumbents) <= 1:
            return (
                40.0,
                f"No stated need at {pos}, but the squad lists only {len(incumbents)} player(s) there.",
                0.7,
            )
        return (
            12.0,
            f"{club.short_name} lists no need at {pos} ({len(incumbents)} players already).",
            0.9,
        )

    score = _PRIORITY_SCORE.get(need.priority, 45.0)
    notes = [f"{need.priority}-priority need at {pos}"]
    if how == "secondary":
        score -= 15
        notes.append("player would play a secondary position")

    profile = need.profile.lower()
    coverage = 0.9
    # age window in profile, e.g. "22-27"
    m = _AGE_RANGE.search(profile)
    if m and player.age is not None:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo <= player.age <= hi:
            score += 5
            notes.append(f"age {player.age} inside requested {lo}-{hi}")
        else:
            gap = min(abs(player.age - lo), abs(player.age - hi))
            score -= min(25, 6 * gap)
            notes.append(f"age {player.age} outside requested {lo}-{hi}")
    m2 = _UNDER.search(profile)
    if m2 and player.age is not None and player.age >= int(m2.group(1)):
        score -= 15
        notes.append(f"profile asks for under-{m2.group(1)}")
    # footedness
    if "left-footed" in profile or "left footed" in profile:
        if player.preferred_foot == "left":
            score += 5
            notes.append("left foot as requested")
        elif player.preferred_foot == "right":
            score -= 12
            notes.append("right-footed, profile asks for a left-footer")
    if "right-footed" in profile or "right footed" in profile:
        if player.preferred_foot == "right":
            score += 3
        elif player.preferred_foot == "left":
            score -= 10
            notes.append("left-footed, profile asks for a right-footer")
    # keyword overlap between profile and style tags
    words = {w for w in re.findall(r"[a-zA-Z\-]{4,}", profile)}
    tag_text = " ".join(player.style_tags)
    hits = sorted(w for w in words if w in tag_text)
    if hits:
        score += min(10, 3 * len(hits))
        notes.append("profile keywords matched: " + ", ".join(hits[:4]))
    return _clamp(score), "; ".join(notes) + ".", coverage


# --------------------------------------------------------------------- statistics
_ATTACKING = {"ST", "LW", "RW", "AM"}
_CREATIVE_MID = {"CM", "AM"}
_DEFENSIVE = {"CB", "DM", "LB", "RB", "GK"}


def _ratio_score(
    actual: Optional[float], target: Optional[float], tolerance: float = 0.35
) -> Optional[float]:
    """100 when actual >= target, decaying to 0 when actual <= target*(1-tolerance)*..."""
    if actual is None or target is None or target <= 0:
        return None
    ratio = actual / target
    if ratio >= 1.15:
        return 100.0
    if ratio >= 1.0:
        return 85.0 + (ratio - 1.0) / 0.15 * 15.0
    floor = 1.0 - tolerance
    if ratio <= floor:
        return max(0.0, 25.0 * ratio / floor)
    return 25.0 + (ratio - floor) / (1.0 - floor) * 60.0


def statistical_fit(player: Player, club: Club, pos: str) -> Score:
    st = player.stats
    bench = club.position_benchmarks.get(pos, {})
    parts: list[float] = []
    notes: list[str] = []
    used = 0
    possible = 0

    # 1) explicit per-90 benchmarks from the club file
    key_map = {
        "goals_p90": st.goals_p90,
        "assists_p90": st.assists_p90,
    }
    for k, actual in key_map.items():
        possible += 1
        target = bench.get(k)
        r = _ratio_score(actual, target)
        if r is not None:
            used += 1
            parts.append(r)
            notes.append(f"{k} {actual:.2f} vs club benchmark {target:.2f}")
    # any extra per-90 stats present on both sides
    for k, target in bench.items():
        if k in key_map or target is None:
            continue
        actual = st.extra.get(k)
        if isinstance(actual, (int, float)) and isinstance(target, (int, float)):
            possible += 1
            used += 1
            higher_is_better = not k.startswith(("fouls", "errors", "goals_conceded"))
            r = _ratio_score(actual, target) if higher_is_better else _ratio_score(target, actual)
            if r is not None:
                parts.append(r)
                notes.append(f"{k} {actual} vs {target}")

    # 2) fallback: compare goal contribution to the club's incumbent starters
    incumbent = club.incumbent_goal_contrib_p90(pos)
    possible += 1
    if pos in _ATTACKING or pos in _CREATIVE_MID:
        gc = st.goal_contrib_p90
        if gc is not None and incumbent is not None:
            used += 1
            r = _ratio_score(gc, incumbent, tolerance=0.5)
            if r is not None:
                parts.append(r)
                notes.append(f"G+A/90 {gc:.2f} vs current {pos} starters {incumbent:.2f}")
        elif gc is not None:
            # league-agnostic sanity anchors per position
            anchor = {"ST": 0.65, "LW": 0.45, "RW": 0.45, "AM": 0.40, "CM": 0.20}.get(pos, 0.2)
            used += 1
            r = _ratio_score(gc, anchor, tolerance=0.6)
            if r is not None:
                parts.append(r)
                notes.append(
                    f"G+A/90 {gc:.2f} vs generic {pos} anchor {anchor:.2f} (no club benchmark)"
                )
    else:
        # defenders/GK: reward minutes/reliability when no benchmark exists
        if st.minutes:
            used += 1
            r = _clamp(st.minutes / 2700 * 100)
            parts.append(r)
            notes.append(f"{st.minutes} league minutes last season (availability proxy)")

    # minutes played as a regularity signal (all positions)
    possible += 1
    if st.minutes:
        used += 1
        parts.append(_clamp(st.minutes / 2500 * 100))

    coverage = used / possible if possible else 0.0
    if not parts:
        return 50.0, "No comparable 2025/26 statistics available — neutral score.", 0.0
    score = sum(parts) / len(parts)
    # penalise stats from clearly weaker competitions when the club is elite
    comp = (st.competition or "").lower()
    tier_penalty = 0.0
    if club.spending_tier() <= 2 and any(
        w in comp
        for w in (
            "eredivisie",
            "liga portugal",
            "pro league",
            "süper lig",
            "super lig",
            "eliteserien",
            "brasileir",
            "primera división argentina",
            "championship",
            "mls",
            "liga mx",
            "austrian",
            "czech",
            "slovak",
            "greek",
            "azerbaijan",
        )
    ):
        tier_penalty = 8.0
        notes.append(f"stats from {st.competition} discounted for a top-tier destination")
    return _clamp(score - tier_penalty), "; ".join(notes) + ".", coverage


# ----------------------------------------------------------------------- tactics
_FORMATION_HINTS = {
    "4-3-3": {"winger", "inverted", "high press", "possession", "single pivot", "no. 8", "no 8"},
    "4-2-3-1": {"no. 10", "no 10", "double pivot", "winger", "target man", "transition"},
    "3-4-3": {"wing-back", "wingback", "back three", "back-three", "inside forward"},
    "3-5-2": {"wing-back", "wingback", "back three", "back-three", "second striker", "mezzala"},
    "4-4-2": {"second striker", "wide midfielder", "compact", "low block", "target man"},
    "4-1-4-1": {"single pivot", "pressing", "box-to-box"},
}


def tactical_fit(player: Player, club: Club) -> Score:
    club_vocab = set(club.style_keywords) | {w for p in club.principles for w in p.split()}
    style_text = (club.playing_style + " " + " ".join(club.style_keywords)).lower()
    formation = (club.formation or "").replace(" ", "")
    tags = set(player.style_tags)
    notes: list[str] = []
    score = 50.0
    coverage = 0.0
    if tags and (style_text.strip() or formation):
        coverage = 1.0
    elif tags or style_text.strip():
        coverage = 0.5

    # direct keyword overlap
    hits = [t for t in tags if any(t in style_text or w in t for w in club_vocab if len(w) > 3)]
    if hits:
        score += min(30, 10 * len(hits))
        notes.append("style overlap: " + ", ".join(sorted(hits)[:4]))

    # formation hints
    for f, hint_words in _FORMATION_HINTS.items():
        if formation.startswith(f.replace("-", "")[:3]) or f in formation:
            fh = [t for t in tags if any(h in t for h in hint_words)]
            if fh:
                score += min(15, 7 * len(fh))
                notes.append(f"suits {club.formation}: " + ", ".join(fh[:3]))
    # best_system explicit match
    for bs in player.best_system:
        if formation and formation in bs.replace(" ", ""):
            score += 10
            notes.append(f"player's preferred system {bs!r} matches")
            break
        if any(k in bs for k in club.style_keywords):
            score += 6
            notes.append(f"preferred system {bs!r} shares club keywords")
            break
    # weaknesses that collide with what the club does
    collisions = [
        w for w in player.weak_in if any(k in w or w in style_text for k in club.style_keywords)
    ]
    if collisions:
        score -= min(30, 15 * len(collisions))
        notes.append("weak in what the club asks: " + ", ".join(collisions[:2]))
    if not notes:
        notes.append("no direct tactical evidence either way")
    return _clamp(score), "; ".join(notes) + ".", coverage


# ----------------------------------------------------------------------- finance
_TIER_MAX_FEE = {1: 120.0, 2: 55.0, 3: 30.0, 4: 12.0}  # typical single-deal ceiling, EUR m
_TIER_MAX_WAGE = {1: 15.0, 2: 6.0, 3: 3.0, 4: 1.2}  # net EUR m / year


def financial(player: Player, club: Club, need: Optional[PositionalNeed]) -> Score:
    fee = player.estimated_fee_eur_m
    if fee is None and player.market_value_eur_m is not None:
        fee = player.market_value_eur_m * 1.15
    wage = player.wage_eur_m_net
    tier = club.spending_tier()
    budget = need.budget_eur_m if need and need.budget_eur_m is not None else _TIER_MAX_FEE[tier]
    wage_cap = (
        need.wage_ceiling_eur_m_net
        if need and need.wage_ceiling_eur_m_net is not None
        else _TIER_MAX_WAGE[tier]
    )
    notes: list[str] = []
    parts: list[float] = []
    cov = 0.0
    if fee is not None:
        cov += 0.6
        if fee <= budget * 0.6:
            parts.append(100.0)
            notes.append(f"fee ~€{fee:.0f}m well inside budget €{budget:.0f}m")
        elif fee <= budget:
            parts.append(85.0)
            notes.append(f"fee ~€{fee:.0f}m inside budget €{budget:.0f}m")
        elif fee <= budget * 1.3:
            parts.append(50.0)
            notes.append(f"fee ~€{fee:.0f}m stretches budget €{budget:.0f}m")
        else:
            parts.append(_clamp(40 - (fee / budget - 1.3) * 60))
            notes.append(f"fee ~€{fee:.0f}m far above budget €{budget:.0f}m")
        if (player.availability or "").startswith("contract running down") or (
            player.contract_until is not None and player.contract_until <= 2027
        ):
            parts[-1] = min(100.0, parts[-1] + 10)
            notes.append("short contract lowers the real price")
    if wage is not None:
        cov += 0.4
        if wage <= wage_cap:
            parts.append(100.0)
            notes.append(f"wage €{wage:.1f}m net fits ceiling €{wage_cap:.1f}m")
        elif wage <= wage_cap * 1.4:
            parts.append(55.0)
            notes.append(f"wage €{wage:.1f}m above ceiling €{wage_cap:.1f}m")
        else:
            parts.append(15.0)
            notes.append(f"wage €{wage:.1f}m far above ceiling €{wage_cap:.1f}m")
    if not parts:
        return 50.0, "No fee or wage data.", 0.0
    return sum(parts) / len(parts), "; ".join(notes) + ".", cov


# ------------------------------------------------------------------ age/contract
def age_contract(player: Player, club: Club) -> Score:
    notes: list[str] = []
    score = 60.0
    cov = 0.0
    if player.age is not None:
        cov += 0.5
        youth_policy = any(
            k in " ".join(club.principles) + " " + (club.transfer_policy or "").lower()
            for k in ("under-25", "u25", "resale", "young", "youth", "develop")
        )
        if youth_policy:
            if player.age <= 24:
                score += 25
                notes.append(f"age {player.age} fits a youth/resale policy")
            elif player.age >= 29:
                score -= 30
                notes.append(f"age {player.age} clashes with a youth/resale policy")
        else:
            if 23 <= player.age <= 29:
                score += 15
                notes.append(f"age {player.age} in prime window")
            elif player.age >= 32:
                score -= 20
                notes.append(f"age {player.age}: short-term signing only")
    if player.contract_until is not None:
        cov += 0.5
        if player.contract_until <= 2027:
            score += 15
            notes.append(f"contract to {player.contract_until}: strong buyer leverage")
        elif player.contract_until >= 2030:
            score -= 10
            notes.append(f"contract to {player.contract_until}: seller holds leverage")
    if not notes:
        notes.append("no age/contract data")
    return _clamp(score), "; ".join(notes) + ".", cov


# ----------------------------------------------------------------------- injuries
def injury_risk(player: Player, club: Club) -> Score:
    days = player.total_days_injured
    n = len(player.injury_history)
    notes: list[str] = []
    if not player.injury_history:
        cov = 0.5 if player.confidence == "low" else 0.8
        return 80.0, "No documented significant injuries (public record).", cov
    score = 100.0 - min(70.0, days / 12.0) - 5.0 * n
    notes.append(f"{n} documented injuries, ~{days} days out")
    serious = [
        i
        for i in player.injury_history
        if any(
            k in str(i.get("type", "")).lower()
            for k in ("acl", "cruciate", "achilles", "meniscus", "fracture")
        )
    ]
    if serious:
        score -= 15
        notes.append("includes a serious structural injury")
    rep = (club.injury_management_reputation or "").lower()
    if rep and any(k in rep for k in ("strong", "good", "excellent", "low injury")):
        score += 5
        notes.append("club has a good injury-management reputation")
    elif rep and any(k in rep for k in ("poor", "crisis", "high injury", "criticis")):
        score -= 5
        notes.append("club has a documented injury-management problem")
    return _clamp(score), "; ".join(notes) + ".", 1.0


# ------------------------------------------------------------------ mental fit
def mental_chemistry(player: Player, club: Club) -> Score:
    m = player.mental
    known = {k: v for k, v in m.items() if isinstance(v, (int, float))}
    if not known:
        return 55.0, "No public-record mental profile; neutral.", 0.0
    char = (club.club_character + " " + club.playing_style).lower()
    high_pressure = any(
        k in char
        for k in (
            "high pressure",
            "intense",
            "demanding",
            "ultras",
            "scrutiny",
            "volatile",
            "hostile",
        )
    )
    dev_club = any(
        k in " ".join(club.principles) for k in ("youth", "develop", "pathway", "resale")
    )
    score = 50.0
    notes: list[str] = []
    avg = sum(known.values()) / len(known)
    score += (avg - 3) * 15
    notes.append(f"avg public mental score {avg:.1f}/5")
    if high_pressure:
        r = known.get("resilience")
        if r is not None:
            score += (r - 3) * 10
            notes.append(f"resilience {r}/5 vs a high-pressure environment")
    if dev_club:
        c = known.get("coachability")
        if c is not None:
            score += (c - 3) * 8
            notes.append(f"coachability {c}/5 for a development club")
    d = known.get("discipline")
    if d is not None and d <= 2:
        score -= 15
        notes.append("documented discipline issues")
    if (
        any(k in char for k in ("leader", "dressing room", "experience"))
        and known.get("leadership", 0) >= 4
    ):
        score += 8
        notes.append("leadership matches what the club says it wants")
    return _clamp(score), "; ".join(notes) + ".", len(known) / 4


# ---------------------------------------------------------------- cultural fit
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
    "eliteserien": "NOR",
    "czech": "CZE",
    "slovak": "SVK",
    "super league greece": "GRE",
    "austrian": "AUT",
    "premyer": "AZE",
    "ukrainian": "UKR",
}
_COUNTRY_LANG = {
    "ENG": "en",
    "ESP": "es",
    "GER": "de",
    "ITA": "it",
    "FRA": "fr",
    "NED": "nl",
    "POR": "pt",
    "TUR": "tr",
    "BEL": "nl",
    "NOR": "no",
    "CZE": "cs",
    "SVK": "sk",
    "GRE": "el",
    "AUT": "de",
    "AZE": "az",
    "UKR": "uk",
}


def cultural_fit(player: Player, club: Club) -> Score:
    score = 55.0
    notes: list[str] = []
    cov = 0.0
    club_langs = set(club.languages)
    if club.country and _COUNTRY_LANG.get(club.country):
        club_langs.add(_COUNTRY_LANG[club.country])
    if player.languages:
        cov += 0.5
        if club_langs & set(player.languages):
            score += 25
            notes.append("shares a working language with the club")
        elif "en" in player.languages and "en" in club_langs:
            score += 10
        else:
            score -= 10
            notes.append("no shared language documented")
    lg = (player.current_club_league or "").lower()
    cur_country = next((c for k, c in _LEAGUE_COUNTRY.items() if k in lg), None)
    if cur_country:
        cov += 0.3
        if cur_country == club.country:
            score += 15
            notes.append("already plays in the destination league")
        elif club.country in {"ENG", "ESP", "GER", "ITA", "FRA"} and cur_country in {
            "ENG",
            "ESP",
            "GER",
            "ITA",
            "FRA",
        }:
            score += 5
            notes.append("moving between top-5 leagues")
    if player.nationality and club.country in player.nationality:
        score += 10
        notes.append("home-country move")
        cov = max(cov, 0.6)
    if not notes:
        notes.append("little cultural-adaptation evidence")
    return _clamp(score), "; ".join(notes) + ".", min(1.0, cov)


# --------------------------------------------------------------------- flags
def collect_flags(player: Player, club: Club, pos: str) -> tuple[list[str], list[str]]:
    """Return (red_flags, human_review). Red flags are hard, sourced facts that a
    human must weigh; human_review are sensitive/soft topics we refuse to score."""
    red: list[str] = []
    review: list[str] = []
    if player.injury_history and any(
        (i.get("season") or "").startswith("2025") and int(i.get("days_out") or 0) >= 90
        for i in player.injury_history
    ):
        red.append("Missed 90+ days last season — medical due diligence required.")
    if (player.mental.get("discipline") or 5) <= 2:
        red.append("Documented discipline record (see mental_profile.notes).")
    if (player.availability or "") == "not for sale":
        red.append("Current club publicly not selling.")
    incumbents = club.players_in(pos)
    young_starters = [p for p in incumbents if (p.role or "") == "starter" and (p.age or 99) <= 23]
    if young_starters:
        red.append(
            f"Would block a young starter ({young_starters[0].name}, {young_starters[0].age}) — "
            f"check pathway politics."
        )
    if player.public_statements:
        review.append(
            "Player has notable public statements on record — check alignment with club "
            "communication policy before approaching (not scored)."
        )
    if club.political_and_social_context:
        review.append(
            "Club has documented institutional/social context — brief the player before any talks "
            "(not scored)."
        )
    if player.confidence == "low" or club.confidence == "low":
        review.append(
            "One side of this match is built on low-confidence public data; verify with the club/player."
        )
    return red, review
