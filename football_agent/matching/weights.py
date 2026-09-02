"""Default dimension weights. They sum to 1.0.

Rationale: the pilot is a *transfer-matching* engine, so on-pitch fit dominates,
but the user's thesis is that chemistry, mentality and context matter and are
under-priced by the current agent market — so those get real weight while still
being capped so that a soft, public-record-only signal can never flip a match on
its own."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Weights:
    need_fit: float = 0.20  # does the club actually need this position/profile?
    statistical_fit: float = 0.20  # output vs the club's positional benchmark / incumbents
    tactical_fit: float = 0.15  # style tags vs coach system & club playing style
    financial: float = 0.15  # fee & wage vs need budget / spending tier
    age_contract: float = 0.05  # age curve vs transfer policy; contract leverage
    injury_risk: float = 0.08  # documented injury history
    mental_chemistry: float = 0.10  # public-record mental profile vs club character
    cultural_fit: float = 0.07  # language, league proximity, public statements

    def as_dict(self) -> dict[str, float]:
        return asdict(self)

    def validate(self) -> None:
        total = sum(self.as_dict().values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0, got {total:.4f}")


DEFAULT_WEIGHTS = Weights()
DEFAULT_WEIGHTS.validate()
