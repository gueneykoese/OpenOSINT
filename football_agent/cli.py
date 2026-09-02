"""python -m football_agent <command>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .commission import quote
from .loader import dataset_status, load_clubs, load_players, validate_dataset
from .matching import MatchEngine
from .report import club_dossier, match_table

_INCLUDE_DEMO = False


def _engine() -> MatchEngine:
    return MatchEngine(load_clubs(), load_players(include_demo=_INCLUDE_DEMO))


def cmd_status(_: argparse.Namespace) -> int:
    st = dataset_status()
    print(
        f"{st['clubs_total']} club files; usable for matching (squad>=15 & needs>=1): "
        f"{len(st['clubs_usable_for_matching'])}"
    )
    print(
        f"{'club':22} {'pot':>3} {'conf':8} {'squad':>5} {'needs':>5} {'opp':>3} {'src':>3}  coach"
    )
    for c in sorted(st["clubs"], key=lambda c: (c["pot"] or 9, c["club_id"])):
        print(
            f"{c['club_id']:22} {c['pot'] or '?':>3} {c['confidence'] or '?':8} {c['squad_size']:>5} "
            f"{c['needs']:>5} {c['opponents']:>3} {c['sources']:>3}  {c['coach'] or '-'}"
        )
    print(f"\n{len(st['players'])} real player files:")
    for p in st["players"]:
        print(
            f"  {p['player_id']:24} {p['position']:3} {p['confidence']:8} {p['current_club'] or '?'}"
        )
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    problems = validate_dataset()
    clubs, players = load_clubs(), load_players()
    print(f"{len(clubs)} clubs, {len(players)} players")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


def cmd_clubs(_: argparse.Namespace) -> int:
    for c in sorted(load_clubs().values(), key=lambda c: (c.pot or 9, c.name)):
        needs = ", ".join(f"{n.position}({n.priority[0]})" for n in c.positional_needs)
        print(
            f"pot{c.pot} {c.club_id:22} {c.short_name:22} {c.coach_name or '?':22} needs: {needs}"
        )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    e = _engine()
    ids = [args.club] if args.club else list(e.clubs)
    outdir = Path(args.out) if args.out else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
    for cid in ids:
        if cid not in e.clubs:
            print(f"unknown club {cid}", file=sys.stderr)
            return 2
        md = club_dossier(e.clubs[cid], e, per_need=args.per_need)
        if outdir:
            (outdir / f"{cid}.md").write_text(md, encoding="utf-8")
        else:
            print(md)
    if outdir:
        print(f"wrote {len(ids)} dossiers to {outdir}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    e = _engine()
    if args.player not in e.players or args.club not in e.clubs:
        print("unknown player or club", file=sys.stderr)
        return 2
    r = e.score(e.players[args.player], e.clubs[args.club])
    if args.json:
        print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(r.summary)
    for d in r.dimensions:
        print(
            f"  {d.label:24} {d.score:5.1f} × {d.weight:.2f} = {d.weighted:5.1f}  | {d.explanation}"
        )
    for f in r.red_flags:
        print("  RED FLAG:", f)
    for h in r.human_review:
        print("  REVIEW:  ", h)
    if args.narrative:
        from .llm import narrate

        print(
            json.dumps(
                narrate(r, e.players[args.player], e.clubs[args.club]), indent=2, ensure_ascii=False
            )
        )
    return 0


def cmd_candidates(args: argparse.Namespace) -> int:
    e = _engine()
    rs = e.rank_players_for_club(args.club, position=args.position, limit=args.limit)
    print(match_table(rs))
    return 0


def cmd_clubs_for(args: argparse.Namespace) -> int:
    e = _engine()
    print(match_table(e.rank_clubs_for_player(args.player, limit=args.limit)))
    return 0


def cmd_mutual(args: argparse.Namespace) -> int:
    e = _engine()
    print(match_table(e.mutual_matches(min_total=args.min_total)))
    return 0


def cmd_commission(args: argparse.Namespace) -> int:
    print(json.dumps(quote(args.fee, args.salary, args.years).to_dict(), indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("football_agent.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="football_agent", description="AI-assisted player-agency matching (UCL 2026/27 pilot)"
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="also load the FICTIONAL demo players from data/demo_players (never real scouting data)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="research status of every club/player file").set_defaults(
        fn=cmd_status
    )
    sub.add_parser("validate", help="validate the JSON dataset").set_defaults(fn=cmd_validate)
    sub.add_parser("clubs", help="list clubs and their stated needs").set_defaults(fn=cmd_clubs)
    s = sub.add_parser("report", help="markdown dossier(s) with recommendations")
    s.add_argument("--club")
    s.add_argument("--out")
    s.add_argument("--per-need", type=int, default=3)
    s.set_defaults(fn=cmd_report)
    s = sub.add_parser("match", help="score one player against one club")
    s.add_argument("player")
    s.add_argument("club")
    s.add_argument("--json", action="store_true")
    s.add_argument(
        "--narrative", action="store_true", help="add a Claude-written memo (needs API key)"
    )
    s.set_defaults(fn=cmd_match)
    s = sub.add_parser("candidates", help="best pool players for a club")
    s.add_argument("club")
    s.add_argument("--position")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(fn=cmd_candidates)
    s = sub.add_parser("clubs-for", help="best clubs for a player")
    s.add_argument("player")
    s.add_argument("--limit", type=int, default=10)
    s.set_defaults(fn=cmd_clubs_for)
    s = sub.add_parser("mutual", help="mutual (club↔player) matches")
    s.add_argument("--min-total", type=float, default=60.0)
    s.set_defaults(fn=cmd_mutual)
    s = sub.add_parser("commission", help="2%% vs market commission quote")
    s.add_argument("fee", type=float)
    s.add_argument("salary", type=float)
    s.add_argument("--years", type=int, default=4)
    s.set_defaults(fn=cmd_commission)
    s = sub.add_parser("serve", help="run the FastAPI backend")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8090)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    global _INCLUDE_DEMO
    _INCLUDE_DEMO = bool(getattr(args, "demo", False))
    return args.fn(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
