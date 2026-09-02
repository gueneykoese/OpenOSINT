"""Load and validate the JSON dataset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .models import POSITIONS, Club, Player

DATA_DIR = Path(__file__).parent / "data"
CLUBS_DIR = DATA_DIR / "clubs"
PLAYERS_DIR = DATA_DIR / "players"
DEMO_PLAYERS_DIR = DATA_DIR / "demo_players"  # clearly-labelled fictional profiles

REQUIRED_CLUB_KEYS = {
    "club_id",
    "name",
    "country",
    "league",
    "ucl_2026_27",
    "head_coach",
    "identity",
    "last_season_2025_26",
    "squad",
    "strengths",
    "weaknesses",
    "positional_needs",
    "position_benchmarks",
    "sources",
    "as_of",
    "data_quality",
}
REQUIRED_PLAYER_KEYS = {
    "player_id",
    "name",
    "age",
    "nationality",
    "position",
    "current_club",
    "contract_until",
    "stats_2025_26",
    "style_profile",
    "mental_profile",
    "injury_history",
    "off_pitch",
    "sources",
    "as_of",
    "data_quality",
}


class DatasetError(ValueError):
    pass


def _read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:  # pragma: no cover - surfaced in validate
            raise DatasetError(f"{path.name}: invalid JSON ({exc})") from exc


def validate_club(d: dict, name: str = "") -> list[str]:
    problems = []
    missing = REQUIRED_CLUB_KEYS - d.keys()
    if missing:
        problems.append(f"{name}: missing keys {sorted(missing)}")
    for p in d.get("squad") or []:
        pos = (p.get("position") or "").upper()
        if pos not in POSITIONS:
            problems.append(f"{name}: squad player {p.get('name')} has unknown position {pos!r}")
    for n in d.get("positional_needs") or []:
        if (n.get("position") or "").upper() not in POSITIONS:
            problems.append(f"{name}: positional need has unknown position {n.get('position')!r}")
        if (n.get("priority") or "").lower() not in ("high", "medium", "low"):
            problems.append(f"{name}: positional need priority {n.get('priority')!r} invalid")
    if not d.get("sources"):
        problems.append(f"{name}: no sources")
    return problems


def validate_player(d: dict, name: str = "") -> list[str]:
    problems = []
    missing = REQUIRED_PLAYER_KEYS - d.keys()
    if missing:
        problems.append(f"{name}: missing keys {sorted(missing)}")
    if (d.get("position") or "").upper() not in POSITIONS:
        problems.append(f"{name}: unknown position {d.get('position')!r}")
    if not d.get("sources"):
        problems.append(f"{name}: no sources")
    return problems


def load_clubs(directory: Path = CLUBS_DIR) -> dict[str, Club]:
    clubs: dict[str, Club] = {}
    for path in sorted(directory.glob("*.json")):
        d = _read_json(path)
        clubs[d["club_id"]] = Club.from_dict(d)
    return clubs


def load_players(directory: Path = PLAYERS_DIR, include_demo: bool = False) -> dict[str, Player]:
    """Load the real transfer-target pool. ``include_demo=True`` adds the fictional
    demo profiles from ``data/demo_players`` (they carry confidence="synthetic")."""
    players: dict[str, Player] = {}
    dirs = [directory] + ([DEMO_PLAYERS_DIR] if include_demo else [])
    for d_ in dirs:
        for path in sorted(d_.glob("*.json")):
            d = _read_json(path)
            players[d["player_id"]] = Player.from_dict(d)
    return players


def dataset_status(clubs_dir: Path = CLUBS_DIR, players_dir: Path = PLAYERS_DIR) -> dict:
    """Per-record research status — what is verified, what is a skeleton."""
    clubs = []
    for path in sorted(clubs_dir.glob("*.json")):
        d = _read_json(path)
        clubs.append(
            {
                "club_id": d.get("club_id"),
                "pot": (d.get("ucl_2026_27") or {}).get("pot"),
                "confidence": (d.get("data_quality") or {}).get("confidence"),
                "coach": (d.get("head_coach") or {}).get("name"),
                "squad_size": len(d.get("squad") or []),
                "needs": len(d.get("positional_needs") or []),
                "opponents": len((d.get("ucl_2026_27") or {}).get("opponents_home") or [])
                + len((d.get("ucl_2026_27") or {}).get("opponents_away") or []),
                "sources": len(d.get("sources") or []),
                "notes": (d.get("data_quality") or {}).get("notes"),
            }
        )
    players = []
    for path in sorted(players_dir.glob("*.json")):
        d = _read_json(path)
        players.append(
            {
                "player_id": d.get("player_id"),
                "position": d.get("position"),
                "current_club": d.get("current_club"),
                "confidence": (d.get("data_quality") or {}).get("confidence"),
                "sources": len(d.get("sources") or []),
            }
        )
    usable = [c for c in clubs if c["squad_size"] >= 15 and c["needs"] >= 1]
    return {
        "clubs": clubs,
        "players": players,
        "clubs_total": len(clubs),
        "clubs_usable_for_matching": [c["club_id"] for c in usable],
    }


def validate_dataset(clubs_dir: Path = CLUBS_DIR, players_dir: Path = PLAYERS_DIR) -> list[str]:
    problems: list[str] = []
    for path in sorted(clubs_dir.glob("*.json")):
        try:
            d = _read_json(path)
        except DatasetError as exc:
            problems.append(str(exc))
            continue
        if d.get("club_id") != path.stem:
            problems.append(f"{path.name}: club_id {d.get('club_id')!r} != filename")
        problems += validate_club(d, path.name)
    for path in sorted(players_dir.glob("*.json")):
        try:
            d = _read_json(path)
        except DatasetError as exc:
            problems.append(str(exc))
            continue
        if d.get("player_id") != path.stem:
            problems.append(f"{path.name}: player_id {d.get('player_id')!r} != filename")
        problems += validate_player(d, path.name)
    return problems


def iter_sources(objs: Iterable[Club | Player]) -> set[str]:
    out: set[str] = set()
    for o in objs:
        out.update(o.sources)
    return out
