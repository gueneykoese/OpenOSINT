"""Commission economics: the thesis is that a 2% flat fee is viable when the
matching work is automated. Numbers are illustrative but the *structure*
(fee on transfer value + fee on gross salary over the contract) mirrors how
intermediary remuneration is actually reported; FIFA's Football Agent
Regulations cap agent fees (3% of salary above USD 200k, 5% below, 10% of a
transfer fee when acting for the selling club), so 2% is inside every cap."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommissionQuote:
    transfer_fee_eur_m: float
    gross_annual_salary_eur_m: float
    contract_years: int
    our_rate: float
    market_rate: float

    @property
    def salary_base_eur_m(self) -> float:
        return self.gross_annual_salary_eur_m * self.contract_years

    @property
    def our_fee_eur_m(self) -> float:
        return round((self.transfer_fee_eur_m + self.salary_base_eur_m) * self.our_rate, 3)

    @property
    def market_fee_eur_m(self) -> float:
        return round((self.transfer_fee_eur_m + self.salary_base_eur_m) * self.market_rate, 3)

    @property
    def saving_eur_m(self) -> float:
        return round(self.market_fee_eur_m - self.our_fee_eur_m, 3)

    def to_dict(self) -> dict:
        return {
            "transfer_fee_eur_m": self.transfer_fee_eur_m,
            "gross_annual_salary_eur_m": self.gross_annual_salary_eur_m,
            "contract_years": self.contract_years,
            "our_rate": self.our_rate,
            "market_rate": self.market_rate,
            "our_fee_eur_m": self.our_fee_eur_m,
            "market_fee_eur_m": self.market_fee_eur_m,
            "saving_for_parties_eur_m": self.saving_eur_m,
        }


def quote(
    transfer_fee_eur_m: float,
    gross_annual_salary_eur_m: float,
    contract_years: int = 4,
    our_rate: float = 0.02,
    market_rate: float = 0.10,
) -> CommissionQuote:
    if contract_years <= 0:
        raise ValueError("contract_years must be positive")
    if not (0 < our_rate < 1 and 0 < market_rate < 1):
        raise ValueError("rates must be fractions between 0 and 1")
    return CommissionQuote(
        transfer_fee_eur_m, gross_annual_salary_eur_m, contract_years, our_rate, market_rate
    )
