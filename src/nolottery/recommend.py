from __future__ import annotations

import re
from dataclasses import dataclass

from .ev import OptionResult, analyze_game
from .metadata import GameMetadata
from .number_format import quick_pick
from .settings import AppSettings


@dataclass(frozen=True)
class Recommendation:
    game_slug: str
    game_name: str
    option: OptionResult
    number_selection: tuple[int, ...]
    number_selection_label: str
    prediction: tuple[int, ...]
    prediction_label: str
    prediction_method: str
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
                    _recommendation(
                        game,
                        option,
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


def _recommendation(game: GameMetadata, option: OptionResult) -> Recommendation:
    prediction = predict_numbers(game.slug, option.option_slug)
    return Recommendation(
        game_slug=game.slug,
        game_name=game.name,
        option=option,
        number_selection=suggest_numbers(game.slug, option.option_slug),
        number_selection_label=suggest_number_label(
            game.slug,
            option.option_slug,
        ),
        prediction=prediction,
        prediction_label=format_number_label(game.slug, option.option_slug, prediction),
        prediction_method="quick-pick-random-no-edge",
        reason=_reason(game.slug, option),
    )


def predict_numbers(game_slug: str, option_slug: str) -> tuple[int, ...]:
    try:
        return quick_pick(game_slug, option_slug)
    except ValueError:
        return ()


def format_number_label(
    game_slug: str,
    option_slug: str,
    numbers: tuple[int, ...],
) -> str:
    if game_slug == "powerball" and len(numbers) == 6:
        return f"White: {_join_numbers(numbers[:5])}; Powerball: {numbers[5]}"
    if game_slug == "mega-millions" and len(numbers) == 6:
        return f"White: {_join_numbers(numbers[:5])}; Mega Ball: {numbers[5]}"
    if game_slug == "lotto-america" and len(numbers) == 6:
        return f"White: {_join_numbers(numbers[:5])}; Star Ball: {numbers[5]}"
    if game_slug == "millionaire-for-life" and len(numbers) == 6:
        return f"White: {_join_numbers(numbers[:5])}; Life Ball: {numbers[5]}"
    if game_slug == "superlotto-plus" and len(numbers) == 6:
        return f"White: {_join_numbers(numbers[:5])}; Mega: {numbers[5]}"
    if game_slug == "daily-derby" and len(numbers) == 4:
        return (
            f"First: {numbers[0]}; Second: {numbers[1]}; "
            f"Third: {numbers[2]}; Race Time Index: {numbers[3]}"
        )
    if game_slug == "lotto" and len(numbers) == 12:
        return (
            f"Play 1: {_join_numbers(numbers[:6])}; "
            f"Play 2: {_join_numbers(numbers[6:])}"
        )
    if numbers:
        return _join_numbers(numbers)
    return "n/a"


def _join_numbers(numbers: tuple[int, ...]) -> str:
    return ", ".join(str(number) for number in numbers)


def suggest_numbers(game_slug: str, option_slug: str) -> tuple[int, ...]:
    digit_count = {
        "florida-pick-2": 2,
        "florida-pick-3": 3,
        "florida-pick-4": 4,
        "florida-pick-5": 5,
        "colorado-pick-3": 3,
        "idaho-pick-3": 3,
        "idaho-pick-4": 4,
        "oregon-pick-4": 4,
        "numbers": 3,
        "texas-pick-3": 3,
        "texas-daily-4": 4,
        "win-4": 4,
    }.get(game_slug)
    if digit_count is not None:
        return tuple(range(1, digit_count + 1))
    if game_slug in {"cashpop", "oregon-cash-pop"}:
        count = _selection_count(option_slug)
        return tuple(range(1, min(count, 15) + 1))
    if game_slug in {"daily-keno", "oregon-keno"}:
        count = _selection_count(option_slug)
        return tuple(range(1, min(count, 80) + 1))
    if game_slug == "powerball":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "mega-millions":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "lotto-america":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "millionaire-for-life":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "idaho-cash":
        return (1, 2, 3, 4, 5)
    if game_slug == "oregon-megabucks":
        return (1, 2, 3, 4, 5, 6)
    if game_slug == "oregon-win-for-life":
        return (1, 2, 3, 4)
    if game_slug == "superlotto-plus":
        return (1, 2, 3, 4, 5, 1)
    if game_slug == "fantasy-5":
        return (1, 2, 3, 4, 5)
    if game_slug == "daily-4":
        return (1, 2, 3, 4)
    if game_slug == "daily-3":
        return (1, 2, 3)
    if game_slug == "daily-derby":
        return (1, 2, 3, 67)
    if game_slug == "hot-spot":
        count = _selection_count(option_slug)
        return tuple(range(1, min(count, 80) + 1))
    if game_slug == "lotto":
        return tuple(range(1, 13))
    if game_slug == "hit-5":
        return (1, 2, 3, 4, 5)
    if game_slug == "match-4":
        return (1, 2, 3, 4)
    if game_slug == "colorado-lotto-plus":
        return (1, 2, 3, 4, 5, 6)
    if game_slug == "colorado-cash-5":
        return (1, 2, 3, 4, 5)
    if game_slug == "texas-lotto":
        return (1, 2, 3, 4, 5, 6)
    if game_slug == "texas-two-step":
        return (1, 2, 3, 4, 1)
    if game_slug == "texas-cash-five":
        return (1, 2, 3, 4, 5)
    if game_slug == "texas-all-or-nothing":
        return tuple(range(1, 13))
    if game_slug == "pick-3":
        if "-3-way-" in option_slug:
            return (1, 1, 2)
        if "pair" in option_slug:
            return (1, 2)
        return (1, 2, 3)
    return ()


def suggest_number_label(game_slug: str, option_slug: str) -> str:
    numbers = suggest_numbers(game_slug, option_slug)
    return format_number_label(game_slug, option_slug, numbers)


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
