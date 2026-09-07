"""Rule-based in-match insights with evidence.

Each rule looks at the current 15-minute window against the team's own earlier
windows (self-referential baselines — the safest thing to do live without a
league-wide model) and emits an Insight: what, how bad, the numbers, what to do.
Insights are inputs for the coach, not verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .models import MatchState, WindowStats

SEV = {"info": 0, "watch": 1, "act": 2}


@dataclass
class Insight:
    key: str
    team: str
    minute: float
    severity: str  # info | watch | act
    title: str
    evidence: str
    suggestion: str
    kind: str  # weakness | strength | fatigue | risk
    position: Optional[str] = None  # position that fixes it (for bench recommendations)
    traits: list[str] = field(default_factory=list)  # what the incoming player should bring
    players: list[str] = field(default_factory=list)  # involved players
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__ | {"metrics": self.metrics}


def _avg(values: list[float]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def analyze(state: MatchState, team: str) -> list[Insight]:
    """Insights for ``team`` at the current minute (needs at least ~10 minutes of data)."""
    out: list[Insight] = []
    minute = state.minute
    widx = state.window_of(minute)
    if minute < 10:
        return out
    opp = state.opponent(team)
    cur: WindowStats = state.window(team, widx)
    opp_cur: WindowStats = state.window(opp, widx)
    prev_idx = [i for i in range(widx) if i in state.windows[team]]
    opp_prev = [state.window(opp, i) for i in prev_idx]

    # 1) flank overload against us
    lanes = dict(opp_cur.attacks_by_lane)
    total = sum(lanes.values())
    if total >= 8:
        # the opponent's LEFT lane (y<33 in their frame) is OUR RIGHT
        our_side = {"left": "sağ", "right": "sol", "centre": "merkez"}
        lane, n = max(lanes.items(), key=lambda kv: kv[1])
        share = n / total
        base_share = _avg(
            [
                w.attacks_by_lane.get(lane, 0) / max(1, sum(w.attacks_by_lane.values()))
                for w in opp_prev
                if sum(w.attacks_by_lane.values()) >= 5
            ]
        )
        if share >= 0.45 and (base_share is None or share >= base_share + 0.1):
            side = our_side.get(lane, lane)
            pos = "RB" if lane == "left" else "LB" if lane == "right" else "DM"
            sev = "act" if share >= 0.55 else "watch"
            out.append(
                Insight(
                    "flank_overload",
                    team,
                    minute,
                    sev,
                    f"Rakip {side} kanadımıza yükleniyor",
                    f"Son pencerede rakip hücumlarının %{share * 100:.0f}'i {side} kanattan ({n}/{total}); "
                    f"önceki pencerelerde %{(base_share or 0) * 100:.0f}. Ortalar: {opp_cur.crosses_by_lane.get(lane, 0)}.",
                    f"{side.capitalize()} beki kanat oyuncusuyla ikile; kanat oyuncusu geri koşuları yapmıyorsa "
                    f"taze, defansif disiplinli bir {pos}/{'RW' if pos == 'RB' else 'LW'} değerlendir.",
                    "weakness",
                    position=pos,
                    traits=["pace", "defensive", "1v1 defending"],
                    metrics={
                        "lane": lane,
                        "share": round(share, 2),
                        "baseline": round(base_share or 0, 2),
                        "crosses": opp_cur.crosses_by_lane.get(lane, 0),
                    },
                )
            )

    # 2) press collapse (PPDA rising vs first windows)
    ppda_now = state.ppda(team, widx)
    ppda_base = _avg([state.ppda(team, i) for i in prev_idx[:2]])
    if ppda_now is not None and ppda_base and ppda_now >= ppda_base * 1.35 and cur.def_actions >= 5:
        sev = "act" if ppda_now >= ppda_base * 1.7 else "watch"
        out.append(
            Insight(
                "press_collapse",
                team,
                minute,
                sev,
                "Pres dağılıyor",
                f"PPDA {ppda_now:.1f} (ilk pencereler {ppda_base:.1f}): rakip her savunma müdahalemiz başına "
                f"%{(ppda_now / ppda_base - 1) * 100:.0f} daha fazla pas yapıyor. Yüksek top kazanma: {cur.high_turnovers}.",
                "Ya bloğu 10 m geri çek ve orta sahayı sıkıştır, ya da presi taze bir 6/8 numarayla yeniden ateşle.",
                "weakness",
                position="DM",
                traits=["pressing", "ball-winning", "stamina"],
                metrics={
                    "ppda": ppda_now,
                    "ppda_baseline": round(ppda_base, 2),
                    "high_turnovers": cur.high_turnovers,
                },
            )
        )

    # 3) fatigue: sprint *rate* decay per player (per-minute, so window boundaries do not lie)
    elapsed_in_window = minute - widx * 15
    if elapsed_in_window >= 6:
        for p in state.on_pitch(team):
            if p.position == "GK" or minute - p.entered_at < 55:
                continue
            wins = [
                i
                for i in sorted(p.sprints_by_window)
                if i < widx and i >= state.window_of(p.entered_at)
            ]
            if len(wins) < 2:
                continue
            base_rate = max(p.sprints_by_window[i] / 15 for i in wins[:2])
            now_rate = p.sprints_by_window.get(widx, 0) / elapsed_in_window
            if base_rate * 15 >= 5 and now_rate <= base_rate * 0.45:
                out.append(
                    Insight(
                        "fatigue",
                        team,
                        minute,
                        "act" if now_rate <= base_rate * 0.3 else "watch",
                        f"{p.name} düşüşte",
                        f"Sprint temposu dakikada {base_rate:.2f} → {now_rate:.2f} (−%{(1 - now_rate / base_rate) * 100:.0f}), "
                        f"{minute - p.entered_at:.0f} dk oynadı"
                        + (f", {p.cards} sarı kart" if p.cards else "")
                        + ".",
                        f"{p.position} pozisyonuna taze oyuncu; sarı kartlı ve yorgun oyuncu ikinci kart riski taşır."
                        if p.cards
                        else f"{p.position} pozisyonuna taze oyuncu planla.",
                        "fatigue",
                        position=p.position,
                        traits=["pace", "stamina"],
                        players=[p.name],
                        metrics={
                            "sprint_rate_base": round(base_rate, 2),
                            "sprint_rate_now": round(now_rate, 2),
                            "minutes": round(minute - p.entered_at),
                            "cards": p.cards,
                        },
                    )
                )

    # 4) striker isolated
    st = [p for p in state.on_pitch(team) if p.position == "ST"]
    if st and minute >= 25:
        p = st[0]
        now_t = p.touches_by_window.get(widx, 0)
        base_t = _avg(
            [p.touches_by_window.get(i, 0) for i in prev_idx if i >= state.window_of(p.entered_at)]
        )
        if base_t and base_t >= 5 and now_t <= base_t * 0.5 and minute % 15 >= 8:
            out.append(
                Insight(
                    "striker_isolated",
                    team,
                    minute,
                    "watch",
                    f"{p.name} izole",
                    f"Bu pencerede {now_t} temas (öncekiler ort. {base_t:.0f}). Hücum bağlantısı kopuk.",
                    "10 numarayı daha yakına al ya da çift forvete geç; bağlantı için taze bir AM/ikinci forvet.",
                    "weakness",
                    position="AM",
                    traits=["link play", "creative", "between the lines"],
                    players=[p.name],
                    metrics={"touches_now": now_t, "touches_baseline": round(base_t, 1)},
                )
            )

    # 5) set-piece / aerial risk
    if opp_cur.corners >= 3 and cur.aerials >= 4:
        won_pct = cur.aerials_won / cur.aerials * 100
        if won_pct < 50:
            out.append(
                Insight(
                    "aerial_risk",
                    team,
                    minute,
                    "watch" if won_pct >= 40 else "act",
                    "Duran top ve hava topu riski",
                    f"Rakip bu pencerede {opp_cur.corners} korner kazandı; hava toplarının %{won_pct:.0f}'ini kazanıyoruz.",
                    "Uzun boylu, hava hakimiyeti yüksek bir stoper/6 numara ile bölgeyi güçlendir.",
                    "risk",
                    position="CB",
                    traits=["aerial", "tall", "defensive"],
                    metrics={"opp_corners": opp_cur.corners, "aerials_won_pct": round(won_pct)},
                )
            )

    # 6) momentum (xG last window)
    dx = cur.xg - opp_cur.xg
    if minute % 15 >= 10 and abs(dx) >= 0.35:
        if dx < 0:
            out.append(
                Insight(
                    "momentum_against",
                    team,
                    minute,
                    "watch",
                    "Momentum rakipte",
                    f"Son pencerede xG {cur.xg:.2f} – {opp_cur.xg:.2f} aleyhimize; top %{state.possession(team, widx) or 0:.0f}.",
                    "Oyunu yavaşlat, topu tut; skor öndeyse bloğu düşür, gerideysen hücum değişikliğini erkene al.",
                    "weakness",
                    metrics={"xg_for": round(cur.xg, 2), "xg_against": round(opp_cur.xg, 2)},
                )
            )
        else:
            out.append(
                Insight(
                    "momentum_for",
                    team,
                    minute,
                    "info",
                    "Baskı işliyor",
                    f"Son pencerede xG {cur.xg:.2f} – {opp_cur.xg:.2f} lehimize; saha eğimi %{state.field_tilt(team, widx) or 0:.0f}.",
                    "Değiştirme; bu blokta ısrar. Sadece yorgunluk uyarısı gelen oyuncuları izle.",
                    "strength",
                    metrics={"xg_for": round(cur.xg, 2), "xg_against": round(opp_cur.xg, 2)},
                )
            )

    # 7) strength: a lane that produces for us
    our_l = dict(cur.attacks_by_lane)
    tot = sum(our_l.values())
    if tot >= 8:
        lane, n = max(our_l.items(), key=lambda kv: kv[1])
        if n / tot >= 0.5 and cur.xg >= 0.3:
            side = {"left": "sol", "right": "sağ", "centre": "merkez"}[lane]
            out.append(
                Insight(
                    "lane_working",
                    team,
                    minute,
                    "info",
                    f"{side.capitalize()} kanat işliyor",
                    f"Hücumlarımızın %{n / tot * 100:.0f}'i {side} taraftan, pencere xG {cur.xg:.2f}.",
                    "Oyunu bu tarafa yönlendirmeye devam; ters kanat için değişiklik düşünüyorsan bu tarafı bozma.",
                    "strength",
                    metrics={"lane": lane, "share": round(n / tot, 2)},
                )
            )
    out.sort(key=lambda i: -SEV[i.severity])
    return out
