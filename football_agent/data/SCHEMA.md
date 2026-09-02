# Data schema (v0.1 — pilot: 2026/27 UEFA Champions League league phase)

All files are UTF-8 JSON. Every numeric stat that comes from the public web MUST
carry provenance in `sources` (URLs) and `as_of` (ISO date). If a value could not
be verified, set it to `null` and explain in `data_quality.notes`. Never invent
numbers.

## clubs/<club_id>.json

```json
{
  "club_id": "real_madrid",                  // snake_case, stable
  "name": "Real Madrid CF",
  "short_name": "Real Madrid",
  "country": "ESP",
  "league": "La Liga",
  "city": "Madrid",
  "ucl_2026_27": {"pot": 1, "qualified_via": "La Liga 2025/26 runner-up",
                  "opponents_home": ["..."], "opponents_away": ["..."]},
  "head_coach": {"name": "...", "since": "2025-06", "nationality": "ESP",
                 "preferred_formation": "4-3-3", "style_keywords": ["high press", "vertical", "..."]},
  "identity": {
    "playing_style": "2-4 sentences, evidence based",
    "principles": ["youth pathway", "buy-to-sell", "Galactico policy", "..."],
    "club_character": "ownership model, fan culture, pressure level, media environment",
    "ownership": "member-owned / state-linked / private equity / family / ...",
    "political_and_social_context": "ONLY publicly documented, institution-level facts (e.g. sponsor controversies, stance statements). No speculation about individuals.",
    "languages": ["es", "en"],
    "wage_structure": "hierarchical / flat / unknown",
    "transfer_policy": "e.g. under-25 resale value; data-led; star-driven",
    "injury_management_reputation": "1-2 sentences if publicly discussed, else null"
  },
  "last_season_2025_26": {
    "league_position": 2, "points": 84, "played": 38, "won": 26, "drawn": 6, "lost": 6,
    "goals_for": 78, "goals_against": 38, "xg_for": null, "xg_against": null,
    "possession_pct": null, "ucl_result": "Quarter-final", "domestic_cup": "Winner",
    "top_scorer": {"name": "...", "goals": 0},
    "top_assister": {"name": "...", "assists": 0}
  },
  "summer_2026_window": {
    "arrivals": [{"name": "...", "from": "...", "fee_eur_m": 0, "position": "CM"}],
    "departures": [{"name": "...", "to": "...", "fee_eur_m": 0, "position": "ST"}],
    "net_spend_eur_m": null
  },
  "squad": [
    {"name": "...", "position": "GK|CB|LB|RB|DM|CM|AM|LW|RW|ST", "secondary_positions": ["RB"],
     "age": 27, "nationality": "BRA", "contract_until": 2028, "shirt_no": 10,
     "role": "starter|rotation|backup|prospect",
     "stats_2025_26": {"apps": 34, "starts": 30, "minutes": 2700, "goals": 5, "assists": 7},
     "injury_flag": "long-term ACL (out until 2027-01) | null"}
  ],
  "strengths": ["...3-6 bullets..."],
  "weaknesses": ["...3-6 bullets..."],
  "positional_needs": [
    {"position": "CB", "priority": "high|medium|low", "profile": "left-footed, ball-playing, 22-27",
     "reason": "why the gap exists (departure, age, injury, tactical)",
     "budget_eur_m": 40, "wage_ceiling_eur_m_net": 8}
  ],
  "position_benchmarks": {
    // Typical output the club gets from a *starter* in that position (per 90 where possible).
    // Used by the matching engine to test statistical fit. null if unknown.
    "ST": {"goals_p90": 0.6, "assists_p90": 0.2, "shots_p90": 3.1, "pressures_p90": null},
    "CM": {"pass_completion_pct": 88, "progressive_passes_p90": 6.5, "tackles_interceptions_p90": 3.0}
  },
  "sources": ["https://..."],
  "as_of": "2026-09-02",
  "data_quality": {"confidence": "high|medium|low", "notes": "what was estimated / unverifiable"}
}
```

## players/<player_id>.json  (transfer-target pool AND represented players)

```json
{
  "player_id": "firstname_lastname",
  "name": "...", "age": 22, "date_of_birth": "2004-03-01", "nationality": ["NGA"],
  "position": "ST", "secondary_positions": ["LW"], "preferred_foot": "right", "height_cm": 185,
  "current_club": "...", "current_club_league": "Eredivisie", "contract_until": 2027,
  "market_value_eur_m": 25, "estimated_fee_eur_m": 30, "wage_eur_m_net": 1.5,
  "release_clause_eur_m": null, "agent_status": "free|represented|represented_by_us",
  "availability": "for sale|open to move|contract running down|not for sale|loan possible",
  "stats_2025_26": {"competition": "Eredivisie", "apps": 31, "starts": 29, "minutes": 2550,
                    "goals": 18, "assists": 6, "xg": null, "xa": null,
                    "shots_p90": null, "key_passes_p90": null, "dribbles_p90": null,
                    "tackles_interceptions_p90": null, "pass_completion_pct": null,
                    "aerials_won_pct": null, "progressive_carries_p90": null},
  "style_profile": {"tags": ["pressing forward", "left-footed", "..."],
                    "best_system": ["4-3-3 high press"], "weak_in": ["low block target man role"]},
  "mental_profile": {"leadership": 3, "coachability": 4, "resilience": 4, "discipline": 4,
                     "notes": "ONLY publicly documented behaviour (cards, public disputes, coach quotes). 1-5 scale, null if unknown."},
  "injury_history": [{"type": "hamstring", "season": "2024/25", "days_out": 45}],
  "off_pitch": {"languages": ["en", "fr"], "family_situation": "public info only or null",
                "public_statements": ["short, sourced summaries of notable public statements"],
                "commercial_profile": "social reach / sponsor appeal, if known",
                "notes": "public record only; no speculation"},
  "sources": ["https://..."], "as_of": "2026-09-02",
  "data_quality": {"confidence": "medium", "notes": "..."}
}
```

## Ethics / compliance notes
* Off-pitch, mental and political fields are restricted to **public record with a
  source**. The engine treats them as *soft* signals with capped weight.
* A player's own consent is required before the platform stores non-public data
  about them; the pilot uses public data only.
