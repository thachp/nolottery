from __future__ import annotations

from dataclasses import dataclass

from .metadata import GameMetadata, PrizeTier, WagerOption
from .settings import AppSettings


@dataclass(frozen=True)
class TierResult:
    label: str
    probability: float
    gross_contribution: float
    after_tax_contribution: float


@dataclass(frozen=True)
class OptionResult:
    option_slug: str
    option_label: str
    ticket_cost: float
    gross_ev: float
    after_tax_ev: float
    net_after_tax_ev: float
    hit_rate: float
    max_recommended_tickets: int
    tiers: tuple[TierResult, ...]


@dataclass(frozen=True)
class AnalysisResult:
    game_slug: str
    game_name: str
    decision: str
    reason: str
    best_option: OptionResult
    options: tuple[OptionResult, ...]


def analyze_game(game: GameMetadata, settings: AppSettings) -> AnalysisResult:
    options = tuple(
        sorted(
            (_analyze_option(option, settings) for option in game.wager_options),
            key=lambda option: option.net_after_tax_ev,
            reverse=True,
        )
    )
    best_option = options[0]
    required_edge = best_option.ticket_cost * settings.bankroll.min_edge_percent
    decision = "PLAY" if best_option.net_after_tax_ev > required_edge else "SKIP"
    reason = (
        f"best after-tax EV is ${best_option.net_after_tax_ev:.2f} "
        f"for {best_option.option_label}"
    )

    return AnalysisResult(
        game_slug=game.slug,
        game_name=game.name,
        decision=decision,
        reason=reason,
        best_option=best_option,
        options=options,
    )


def _analyze_option(option: WagerOption, settings: AppSettings) -> OptionResult:
    tiers = tuple(_analyze_tier(tier, settings) for tier in option.prize_tiers)
    gross_ev = sum(tier.gross_contribution for tier in tiers)
    after_tax_ev = sum(tier.after_tax_contribution for tier in tiers)
    net_after_tax_ev = after_tax_ev - option.ticket_cost
    affordable_tickets = int(settings.bankroll.max_session_spend // option.ticket_cost)
    max_recommended_tickets = min(
        affordable_tickets,
        settings.bankroll.max_tickets_per_game,
    )

    return OptionResult(
        option_slug=option.slug,
        option_label=option.label,
        ticket_cost=option.ticket_cost,
        gross_ev=gross_ev,
        after_tax_ev=after_tax_ev,
        net_after_tax_ev=net_after_tax_ev,
        hit_rate=sum(tier.probability for tier in option.prize_tiers),
        max_recommended_tickets=max_recommended_tickets,
        tiers=tiers,
    )


def _analyze_tier(tier: PrizeTier, settings: AppSettings) -> TierResult:
    after_tax_prize = tier.prize
    if tier.prize >= settings.tax.apply_tax_above:
        after_tax_prize = tier.prize * (
            1 - settings.tax.federal_tax_rate - settings.tax.state_tax_rate
        )
    return TierResult(
        label=tier.label,
        probability=tier.probability,
        gross_contribution=tier.probability * tier.prize,
        after_tax_contribution=tier.probability * after_tax_prize,
    )

