"""Build the self-contained head-coach live panel (timeline embedded)."""

from __future__ import annotations

import json
from pathlib import Path

from ..loader import load_clubs, load_players
from .timeline import build_timeline

TEMPLATE = Path(__file__).parent / "template.html"


def build(out_path: Path, home: str = "arsenal", away: str = "real_madrid", seed: int = 4) -> Path:
    clubs, pool = load_clubs(), load_players()
    tl = build_timeline(clubs[home], clubs[away], focus=home, pool=pool, seed=seed)
    data = json.dumps(tl, ensure_ascii=False, default=str).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
