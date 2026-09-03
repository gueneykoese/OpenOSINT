"""Success-bonus plans for represented players.

Business rule (from the agency's thesis): when a player we placed succeeds at the
new club, we pay the player a bonus. "Success" is not vague — it is defined by the
very dimensions that made the engine recommend the club, turned into measurable,
club-specific targets for the first season. Default pool: 5% of gross annual salary
(EUR 50k on a EUR 1m salary).

Design
* Targets are derived from the MatchResult: the dimensions that carried the match
  (highest weighted contribution, score >= 55) become KPIs. Each KPI carries the
  metric, the threshold, how to verify it, and its share of the pool (proportional
  to the engine weight of its dimension).
* Attainment is linear between a floor (70% of target → 0) and the target (100%),
  capped at 100%. Partial success pays partially.
* Club-level targets (league position at least last season's, UCL league-phase
  top 24) act as a multiplier on the whole pool (+25% if both met, +10% if one).
* Two payout modes: ``bonus`` (cash to the player) and ``fee_rebate`` (the same
  amount returned as a discount on our own commission). The rebate form avoids
  any question under FIFA's Football Agent Regulations about agents paying
  clients; the plan flags this and the agency's counsel decides.
* Economics are reported next to the plan: the bonus is paid out of our 2%
  commission, so the plan shows what share of our fee we put at risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .commission import quote
from .models import Club, MatchResult, Player

DEFAULT_BONUS_RATE = 0.05  # 5% of gross annual salary
NET_TO_GROSS = 1.9  # crude EU-average uplift when only net wage is known
ATTAINMENT_FLOOR = 0.70  # below 70% of target nothing is paid
TEAM_MULTIPLIER = {0: 1.0, 1: 1.10, 2: 1.25}

_ATTACKING = {"ST", "LW", "RW", "AM"}
_MIDFIELD = {"CM", "DM"}


@dataclass
class Kpi:
    key: str
    dimension: str
    title: str
    metric: str
    target: float
    unit: str
    verify: str
    share: float  # fraction of the pool
    rationale: str
    higher_is_better: bool = True

    def attainment(self, actual: Optional[float]) -> float:
        if actual is None:
            return 0.0
        if self.higher_is_better:
            ratio = actual / self.target if self.target else 0.0
        else:
            ratio = self.target / actual if actual else 1.0
        if ratio >= 1.0:
            return 1.0
        if ratio <= ATTAINMENT_FLOOR:
            return 0.0
        return round((ratio - ATTAINMENT_FLOOR) / (1.0 - ATTAINMENT_FLOOR), 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "dimension": self.dimension,
            "title": self.title,
            "metric": self.metric,
            "target": self.target,
            "unit": self.unit,
            "higher_is_better": self.higher_is_better,
            "verify": self.verify,
            "share": round(self.share, 3),
            "rationale": self.rationale,
        }


@dataclass
class TeamTarget:
    key: str
    title: str
    target: str
    verify: str

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "title": self.title, "target": self.target, "verify": self.verify}


@dataclass
class BonusPlan:
    player_id: str
    club_id: str
    position: str
    gross_salary_eur_m: float
    bonus_rate: float
    mode: str
    kpis: list[Kpi]
    team_targets: list[TeamTarget]
    notes: list[str] = field(default_factory=list)
    economics: dict[str, Any] = field(default_factory=dict)

    @property
    def pool_eur_m(self) -> float:
        return round(self.gross_salary_eur_m * self.bonus_rate, 4)

    def evaluate(
        self, actuals: dict[str, Optional[float]], team_targets_met: int = 0
    ) -> dict[str, Any]:
        """Compute the payout for one season from measured values.

        ``actuals`` maps kpi.key -> measured value; missing keys count as not met."""
        rows = []
        earned = 0.0
        for k in self.kpis:
            att = k.attainment(actuals.get(k.key))
            amount = self.pool_eur_m * k.share * att
            earned += amount
            rows.append(
                {
                    "key": k.key,
                    "title": k.title,
                    "target": k.target,
                    "actual": actuals.get(k.key),
                    "attainment": att,
                    "payout_eur_m": round(amount, 4),
                }
            )
        mult = TEAM_MULTIPLIER.get(max(0, min(2, team_targets_met)), 1.0)
        total = round(earned * mult, 4)
        return {
            "pool_eur_m": self.pool_eur_m,
            "kpis": rows,
            "team_targets_met": team_targets_met,
            "team_multiplier": mult,
            "payout_eur_m": total,
            "mode": self.mode,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "club_id": self.club_id,
            "position": self.position,
            "gross_salary_eur_m": self.gross_salary_eur_m,
            "bonus_rate": self.bonus_rate,
            "pool_eur_m": self.pool_eur_m,
            "mode": self.mode,
            "kpis": [k.to_dict() for k in self.kpis],
            "team_targets": [t.to_dict() for t in self.team_targets],
            "attainment_floor": ATTAINMENT_FLOOR,
            "team_multiplier": TEAM_MULTIPLIER,
            "economics": self.economics,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- build
def _kpi_for(dim_key: str, r: MatchResult, player: Player, club: Club) -> Optional[Kpi]:
    pos = r.position
    bench = club.position_benchmarks.get(pos, {})
    if dim_key == "need_fit":
        return Kpi(
            "starter_share",
            dim_key,
            "Kalıcı ilk 11 oyuncusu olmak",
            f"{pos} pozisyonunda lig dakikası payı",
            60.0,
            "% (mümkün lig dakikalarının)",
            "Lig maç raporları (resmi lig verisi): oynanan dakika / takımın toplam lig dakikası",
            0.0,
            "Kulüp bu pozisyonda açık ihtiyaç bildirdi; eşleşmenin ilk gerekçesi burayı doldurmak.",
        )
    if dim_key == "statistical_fit":
        if pos in _ATTACKING:
            target = (
                bench.get("goals_p90")
                and bench.get("assists_p90")
                and (bench["goals_p90"] + bench["assists_p90"])
            )
            if not target:
                target = (
                    club.incumbent_goal_contrib_p90(pos)
                    or {"ST": 0.6, "LW": 0.45, "RW": 0.45, "AM": 0.4}[pos]
                )
            return Kpi(
                "goal_contrib_p90",
                dim_key,
                "Hücum üretimini korumak",
                "Gol + asist / 90 dk (lig)",
                round(float(target), 2),
                "G+A / 90",
                "Resmi lig istatistiği veya lisanslı sağlayıcı (Opta/StatsBomb); min. 900 dakika",
                0.0,
                "Eşleşmede istatistik boyutu yüksekti; hedef kulübün pozisyon kıyas değeri ya da mevcut ilk 11'in ortalaması.",
            )
        if pos in _MIDFIELD:
            target = bench.get("pass_completion_pct") or 85.0
            return Kpi(
                "pass_completion",
                dim_key,
                "Top güvenliği ve ilerletme",
                "Pas isabeti (lig)",
                float(target),
                "%",
                "Lisanslı sağlayıcı; min. 900 dakika",
                0.0,
                "Orta saha için istatistik boyutu pas güvenliği üzerinden tanımlandı.",
            )
        # defenders / GK: availability-weighted minutes
        return Kpi(
            "league_minutes",
            dim_key,
            "Düzenli oynamak",
            "Lig dakikası",
            2200.0,
            "dakika",
            "Resmi lig verisi",
            0.0,
            "Savunma/kaleci için istatistik boyutu güvenilir dakika üzerinden ölçülür.",
        )
    if dim_key == "tactical_fit":
        return Kpi(
            "system_trust",
            dim_key,
            "Hocanın sisteminde güven kazanmak",
            "Sezonun ikinci yarısında ilk 11 başlangıç payı",
            65.0,
            "% (2. yarı lig maçları)",
            "Lig maç kadroları; ocak sonrası maçlar",
            0.0,
            f"Stil etiketleri {club.formation or 'kulüp sistemi'} ile örtüştü; kanıt, hocanın ikinci yarıda da tercih etmesi.",
        )
    if dim_key == "mental_chemistry":
        return Kpi(
            "discipline",
            dim_key,
            "Disiplin ve soyunma odası",
            "Kırmızı kart + belgelenmiş kamuya açık anlaşmazlık sayısı",
            0.0,
            "adet (düşük iyi)",
            "Resmi disiplin kayıtları; kulüp/oyuncu resmi açıklamaları",
            0.0,
            "Mental profil kulüp karakteriyle uyumlu görüldü; hedef bunu sezon boyunca korumak.",
            higher_is_better=False,
        )
    if dim_key == "injury_risk":
        return Kpi(
            "availability",
            dim_key,
            "Sahada kalmak",
            "Sakatlıksız geçen maç günü payı",
            85.0,
            "% (tüm resmi maçlar)",
            "Kulüp sakatlık raporları / resmi maç kadroları",
            0.0,
            "Sakatlık geçmişi temiz görüldü; hedef bunun yeni yük altında da sürmesi.",
        )
    if dim_key == "cultural_fit":
        lang = {
            "ENG": "İngilizce",
            "ESP": "İspanyolca",
            "GER": "Almanca",
            "ITA": "İtalyanca",
            "FRA": "Fransızca",
            "NED": "Hollandaca",
            "POR": "Portekizce",
            "TUR": "Türkçe",
        }.get(club.country or "", "kulüp ülkesinin dili")
        return Kpi(
            "integration",
            dim_key,
            "Kültürel entegrasyon",
            f"{lang} B1 sertifikası + yerel dilde en az 3 medya görüşmesi",
            1.0,
            "tamamlandı (1) / tamamlanmadı (0)",
            "Sertifika belgesi; kulüp medya arşivi",
            0.0,
            "Hofstede mesafesi ve dil boyutu eşleşmeyi destekledi; entegrasyon hedefi bunu somutlar.",
        )
    return None  # financial / age_contract are not player-controlled


def build_plan(
    r: MatchResult,
    player: Player,
    club: Club,
    gross_salary_eur_m: Optional[float] = None,
    bonus_rate: float = DEFAULT_BONUS_RATE,
    mode: str = "bonus",
    max_kpis: int = 4,
    transfer_fee_eur_m: Optional[float] = None,
    contract_years: int = 4,
) -> BonusPlan:
    notes: list[str] = []
    if gross_salary_eur_m is None:
        if player.wage_eur_m_net is not None:
            gross_salary_eur_m = round(player.wage_eur_m_net * NET_TO_GROSS, 3)
            notes.append(
                f"Brüt maaş net × {NET_TO_GROSS} varsayımıyla türetildi; sözleşmedeki brüt rakamla değiştirin."
            )
        else:
            gross_salary_eur_m = 1.0
            notes.append("Maaş verisi yok; 1.0 M€ brüt varsayıldı (yalnızca örnek).")
    # pick driving dimensions
    ranked = sorted(r.dimensions, key=lambda d: d.weighted, reverse=True)
    chosen = []
    for d in ranked:
        if d.key in ("financial", "age_contract") or d.score < 55:
            continue
        k = _kpi_for(d.key, r, player, club)
        if k:
            k.share = d.weight
            chosen.append(k)
        if len(chosen) >= max_kpis:
            break
    if not chosen:  # weak match: fall back to the two universal KPIs
        chosen = [_kpi_for("need_fit", r, player, club), _kpi_for("injury_risk", r, player, club)]
        for k in chosen:
            k.share = 0.5
        notes.append(
            "Eşleşme zayıf: yalnızca evrensel hedefler (ilk 11 payı, sahada kalma) kullanıldı."
        )
    total_w = sum(k.share for k in chosen)
    for k in chosen:
        k.share = k.share / total_w
    # team targets from the club dossier
    ls = club.last_season or {}
    pos_target = ls.get("league_position")
    team = [
        TeamTarget(
            "league_position",
            "Lig sıralaması",
            f"En az {pos_target}. sıra (geçen sezon)"
            if pos_target
            else "Geçen sezonki sıralamayı korumak",
            "Resmi lig tablosu, sezon sonu",
        ),
        TeamTarget(
            "ucl_progress",
            "Şampiyonlar Ligi",
            "Lig aşamasında ilk 24 (eleme turuna kalmak)",
            "UEFA resmi sıralama, Ocak 2027",
        ),
    ]
    if mode == "bonus":
        notes.append(
            "Menajerin oyuncuya nakit ödeme yapması FIFA Futbol Menajerliği Yönetmeliği ve ulusal federasyon kurallarına göre hukuki incelemeden geçmeli; sorun çıkarsa 'fee_rebate' (komisyon indirimi) modu aynı ekonomik etkiyi verir."
        )
    fee = (
        transfer_fee_eur_m
        if transfer_fee_eur_m is not None
        else (player.estimated_fee_eur_m or 0.0)
    )
    q = quote(fee, gross_salary_eur_m, contract_years)
    pool = round(gross_salary_eur_m * bonus_rate, 4)
    econ = {
        "our_fee_eur_m": q.our_fee_eur_m,
        "bonus_pool_per_season_eur_m": pool,
        "max_bonus_over_contract_eur_m": round(pool * contract_years * TEAM_MULTIPLIER[2], 4),
        "max_bonus_share_of_fee_pct": round(
            pool * contract_years * TEAM_MULTIPLIER[2] / q.our_fee_eur_m * 100, 1
        )
        if q.our_fee_eur_m
        else None,
        "assumptions": {
            "transfer_fee_eur_m": fee,
            "contract_years": contract_years,
            "market_rate": q.market_rate,
        },
    }
    if econ["max_bonus_share_of_fee_pct"] and econ["max_bonus_share_of_fee_pct"] > 60:
        notes.append(
            "Tam başarı senaryosunda bonus, komisyonumuzun %60'ından fazlasını geri verir; oran veya süre gözden geçirilmeli."
        )
    return BonusPlan(
        player.player_id,
        club.club_id,
        r.position,
        gross_salary_eur_m,
        bonus_rate,
        mode,
        chosen,
        team,
        notes,
        econ,
    )
