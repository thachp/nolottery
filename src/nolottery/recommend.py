from __future__ import annotations

import re
from dataclasses import dataclass

from .ev import OptionResult, analyze_game
from .metadata import GameMetadata
from .settings import AppSettings


@dataclass(frozen=True)
class Recommendation:
    game_slug: str
    game_name: str
    option: OptionResult
    number_selection: tuple[int, ...]
    number_selection_label: str
    reason: str


def recommend_highest_hit_rate(
    games: tuple[GameMetadata, ...],
    settings: AppSettings,
    budget: float,
) -> tuple[Recommendation, ...]:
    recommendations: list[Recommendation] = []
    for game in games:
        analysis = analyze_game(game, settings)
        for option in analysis.options:
            if option.ticket_cost <= budget:
                recommendations.append(
                    Recommendation(
                        game_slug=game.slug,
                        game_name=game.name,
                        option=option,
                        number_selection=suggest_numbers(game.slug, option.option_slug),
                        number_selection_label=suggest_number_label(
                            game.slug,
                            option.option_slug,
                        ),
                        reason=_reason(game.slug, option),
                    )
                )

    return tuple(
        sorted(
            recommendations,
            key=lambda recommendation: (
                _effective_hit_rate(recommendation),
                recommendation.option.net_after_tax_ev,
                -recommendation.option.ticket_cost,
            ),
            reverse=True,
        )
    )


def suggest_numbers(game_slug: str, option_slug: str) -> tuple[int, ...]:
    if game_slug == "cashpop":
        count = _selection_count(option_slug)
        return tuple(range(1, min(count, 15) + 1))
    if game_slug == "daily-keno":
        count = _selection_count(option_slug)
        return tuple(range(1, min(count, 80) + 1))
    if game_slug == "powerball":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "mega-millions":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "lotto":
        return tuple(range(1, 13))
    if game_slug == "hit-5":
        return (1, 2, 3, 4, 5)
    if game_slug == "match-4":
        return (1, 2, 3, 4)
    if game_slug == "pick-3":
        if "-3-way-" in option_slug:
            return (1, 1, 2)
        if "pair" in option_slug:
            return (1, 2)
        return (1, 2, 3)
    return ()


def suggest_number_label(game_slug: str, option_slug: str) -> str:
    numbers = suggest_numbers(game_slug, option_slug)
    if game_slug == "powerball":
        return "White: 1, 2, 3, 4, 5; Powerball: 1"
    if game_slug == "mega-millions":
        return "White: 1, 2, 3, 4, 5; Mega Ball: 1"
    if game_slug == "lotto":
        return "Play 1: 1, 2, 3, 4, 5, 6; Play 2: 7, 8, 9, 10, 11, 12"
    if game_slug == "pick-3" and "pair" in option_slug:
        return "1, 2"
    if numbers:
        return ", ".join(str(number) for number in numbers)
    return "n/a"


def displayed_hit_rate(recommendation: Recommendation) -> float:
    return _effective_hit_rate(recommendation)


def _effective_hit_rate(recommendation: Recommendation) -> float:
    if recommendation.game_slug == "cashpop" and recommendation.option.option_slug == "15-pop":
        return 1.0
    return min(recommendation.option.hit_rate, 1.0)


def _selection_count(option_slug: str) -> int:
    if option_slug == "one-pop":
        return 1
    match = re.match(r"^(\d+)-", option_slug)
    if match is None:
        return 0
    return int(match.group(1))


def _reason(game_slug: str, option: OptionResult) -> str:
    if game_slug == "cashpop" and option.option_slug == "15-pop":
        return "all Cash Pop numbers are covered, so any draw wins a prize"
    return "highest hit rate among single-ticket options within the budget"
