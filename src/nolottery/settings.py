from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaxSettings:
    federal_tax_rate: float = 0.24
    state_tax_rate: float = 0.0
    apply_tax_above: float = 600.0


@dataclass(frozen=True)
class BankrollSettings:
    bankroll: float = 100.0
    max_session_spend: float = 10.0
    max_tickets_per_game: int = 10
    min_edge_percent: float = 0.0


@dataclass(frozen=True)
class AppSettings:
    tax: TaxSettings = TaxSettings()
    bankroll: BankrollSettings = BankrollSettings()

