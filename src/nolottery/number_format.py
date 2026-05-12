from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Protocol


class RandomSource(Protocol):
    def sample(self, population, k: int): ...

    def randrange(self, start: int, stop: int | None = None): ...

    def shuffle(self, x: list[int]) -> None: ...


@dataclass(frozen=True)
class NumberPool:
    name: str
    minimum: int
    maximum: int
    count: int
    ordered: bool = False
    allow_repeats: bool = False


@dataclass(frozen=True)
class NumberFormat:
    game_slug: str
    pools: tuple[NumberPool, ...]


NUMBER_FORMATS: dict[str, NumberFormat] = {
    "powerball": NumberFormat(
        game_slug="powerball",
        pools=(
            NumberPool("white", 1, 69, 5),
            NumberPool("powerball", 1, 26, 1),
        ),
    ),
    "mega-millions": NumberFormat(
        game_slug="mega-millions",
        pools=(
            NumberPool("white", 1, 70, 5),
            NumberPool("mega-ball", 1, 24, 1),
        ),
    ),
    "lotto-america": NumberFormat(
        game_slug="lotto-america",
        pools=(
            NumberPool("white", 1, 52, 5),
            NumberPool("star-ball", 1, 10, 1),
        ),
    ),
    "millionaire-for-life": NumberFormat(
        game_slug="millionaire-for-life",
        pools=(
            NumberPool("white", 1, 58, 5),
            NumberPool("life-ball", 1, 5, 1),
        ),
    ),
    "lucky-for-life": NumberFormat(
        game_slug="lucky-for-life",
        pools=(
            NumberPool("white", 1, 48, 5),
            NumberPool("lucky-ball", 1, 18, 1),
        ),
    ),
    "arkansas-cash-3": NumberFormat(
        game_slug="arkansas-cash-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "arkansas-cash-4": NumberFormat(
        game_slug="arkansas-cash-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "dc-3": NumberFormat(
        game_slug="dc-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "dc-4": NumberFormat(
        game_slug="dc-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "dc-5": NumberFormat(
        game_slug="dc-5",
        pools=(NumberPool("digits", 0, 9, 5, ordered=True, allow_repeats=True),),
    ),
    "georgia-cash-3": NumberFormat(
        game_slug="georgia-cash-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "georgia-cash-4": NumberFormat(
        game_slug="georgia-cash-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "georgia-five": NumberFormat(
        game_slug="georgia-five",
        pools=(NumberPool("digits", 0, 9, 5, ordered=True, allow_repeats=True),),
    ),
    "arkansas-lotto": NumberFormat(
        game_slug="arkansas-lotto",
        pools=(NumberPool("numbers", 1, 40, 6),),
    ),
    "arkansas-natural-state-jackpot": NumberFormat(
        game_slug="arkansas-natural-state-jackpot",
        pools=(NumberPool("numbers", 1, 39, 5),),
    ),
    "idaho-cash": NumberFormat(
        game_slug="idaho-cash",
        pools=(NumberPool("white", 1, 45, 5),),
    ),
    "idaho-pick-3": NumberFormat(
        game_slug="idaho-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "idaho-pick-4": NumberFormat(
        game_slug="idaho-pick-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "oregon-megabucks": NumberFormat(
        game_slug="oregon-megabucks",
        pools=(NumberPool("white", 1, 48, 6),),
    ),
    "oregon-cash-pop": NumberFormat(
        game_slug="oregon-cash-pop",
        pools=(NumberPool("numbers", 1, 15, 1),),
    ),
    "oregon-pick-4": NumberFormat(
        game_slug="oregon-pick-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "oregon-win-for-life": NumberFormat(
        game_slug="oregon-win-for-life",
        pools=(NumberPool("numbers", 1, 77, 4),),
    ),
    "superlotto-plus": NumberFormat(
        game_slug="superlotto-plus",
        pools=(
            NumberPool("white", 1, 47, 5),
            NumberPool("mega", 1, 27, 1),
        ),
    ),
    "fantasy-5": NumberFormat(
        game_slug="fantasy-5",
        pools=(NumberPool("white", 1, 39, 5),),
    ),
    "daily-4": NumberFormat(
        game_slug="daily-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "daily-3": NumberFormat(
        game_slug="daily-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "florida-pick-2": NumberFormat(
        game_slug="florida-pick-2",
        pools=(NumberPool("digits", 0, 9, 2, ordered=True, allow_repeats=True),),
    ),
    "florida-pick-3": NumberFormat(
        game_slug="florida-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "florida-pick-4": NumberFormat(
        game_slug="florida-pick-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "florida-pick-5": NumberFormat(
        game_slug="florida-pick-5",
        pools=(NumberPool("digits", 0, 9, 5, ordered=True, allow_repeats=True),),
    ),
    "numbers": NumberFormat(
        game_slug="numbers",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "win-4": NumberFormat(
        game_slug="win-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "quick-draw": NumberFormat(
        game_slug="quick-draw",
        pools=(NumberPool("numbers", 1, 80, 20),),
    ),
    "pick-10": NumberFormat(
        game_slug="pick-10",
        pools=(NumberPool("numbers", 1, 80, 10),),
    ),
    "hit-5": NumberFormat(
        game_slug="hit-5",
        pools=(NumberPool("white", 1, 42, 5),),
    ),
    "match-4": NumberFormat(
        game_slug="match-4",
        pools=(NumberPool("white", 1, 24, 4),),
    ),
    "minnesota-pick-3": NumberFormat(
        game_slug="minnesota-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "michigan-daily-3": NumberFormat(
        game_slug="michigan-daily-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "michigan-daily-4": NumberFormat(
        game_slug="michigan-daily-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "mississippi-cash-3": NumberFormat(
        game_slug="mississippi-cash-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "mississippi-cash-4": NumberFormat(
        game_slug="mississippi-cash-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "colorado-lotto-plus": NumberFormat(
        game_slug="colorado-lotto-plus",
        pools=(NumberPool("numbers", 1, 40, 6),),
    ),
    "colorado-cash-5": NumberFormat(
        game_slug="colorado-cash-5",
        pools=(NumberPool("numbers", 1, 32, 5),),
    ),
    "colorado-pick-3": NumberFormat(
        game_slug="colorado-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "texas-lotto": NumberFormat(
        game_slug="texas-lotto",
        pools=(NumberPool("numbers", 1, 54, 6),),
    ),
    "texas-two-step": NumberFormat(
        game_slug="texas-two-step",
        pools=(
            NumberPool("white", 1, 35, 4),
            NumberPool("bonus-ball", 1, 35, 1),
        ),
    ),
    "texas-cash-five": NumberFormat(
        game_slug="texas-cash-five",
        pools=(NumberPool("numbers", 1, 35, 5),),
    ),
    "texas-all-or-nothing": NumberFormat(
        game_slug="texas-all-or-nothing",
        pools=(NumberPool("numbers", 1, 24, 12),),
    ),
    "texas-pick-3": NumberFormat(
        game_slug="texas-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "texas-daily-4": NumberFormat(
        game_slug="texas-daily-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "nebraska-pick-5": NumberFormat(
        game_slug="nebraska-pick-5",
        pools=(NumberPool("numbers", 1, 40, 5),),
    ),
    "nebraska-pick-4": NumberFormat(
        game_slug="nebraska-pick-4",
        pools=(NumberPool("digits", 0, 9, 4, ordered=True, allow_repeats=True),),
    ),
    "nebraska-pick-3": NumberFormat(
        game_slug="nebraska-pick-3",
        pools=(NumberPool("digits", 0, 9, 3, ordered=True, allow_repeats=True),),
    ),
    "nebraska-myday": NumberFormat(
        game_slug="nebraska-myday",
        pools=(
            NumberPool("month", 1, 12, 1),
            NumberPool("day", 1, 31, 1),
            NumberPool("year", 0, 99, 1),
        ),
    ),
    "nebraska-2by2": NumberFormat(
        game_slug="nebraska-2by2",
        pools=(
            NumberPool("red", 1, 26, 2),
            NumberPool("white", 1, 26, 2),
        ),
    ),
}


def quick_pick(
    game_slug: str,
    option_slug: str,
    *,
    rng: RandomSource | None = None,
) -> tuple[int, ...]:
    source = rng if rng is not None else random.SystemRandom()
    if game_slug in {"cashpop", "georgia-cash-pop", "oregon-cash-pop"}:
        count = _selection_count(option_slug)
        if count >= 15:
            return tuple(range(1, 16))
        return tuple(sorted(source.sample(range(1, 16), count)))
    if game_slug in {"daily-keno", "oregon-keno"}:
        return tuple(sorted(source.sample(range(1, 81), _selection_count(option_slug))))
    if game_slug == "hot-spot":
        return tuple(sorted(source.sample(range(1, 81), _selection_count(option_slug))))
    if game_slug == "daily-derby":
        horses = tuple(source.sample(range(1, 13), 3))
        return (*horses, source.randrange(0, 1001))
    if game_slug == "lotto":
        play_one = sorted(source.sample(range(1, 50), 6))
        play_two = sorted(source.sample(range(1, 50), 6))
        return tuple(play_one + play_two)
    if game_slug == "pick-3":
        return _pick3_quick_pick(source, option_slug)

    try:
        number_format = NUMBER_FORMATS[game_slug]
    except KeyError as exc:
        raise ValueError(f"unknown game: {game_slug}") from exc
    return tuple(
        number
        for pool in number_format.pools
        for number in _pick_pool(source, pool)
    )


def _pick_pool(source: RandomSource, pool: NumberPool) -> tuple[int, ...]:
    if pool.allow_repeats:
        numbers = tuple(
            source.randrange(pool.minimum, pool.maximum + 1)
            for _ in range(pool.count)
        )
    else:
        numbers = tuple(
            source.sample(range(pool.minimum, pool.maximum + 1), pool.count)
        )
    if pool.ordered:
        return numbers
    return tuple(sorted(numbers))


def _pick3_quick_pick(source: RandomSource, option_slug: str) -> tuple[int, ...]:
    if "-3-way-" in option_slug:
        digit = source.randrange(0, 10)
        other = _different_digit(source, digit)
        return tuple(sorted((digit, digit, other)))
    if "pair" in option_slug:
        return (source.randrange(0, 10), source.randrange(0, 10))
    return tuple(source.randrange(0, 10) for _ in range(3))


def _different_digit(source: RandomSource, digit: int) -> int:
    other = source.randrange(0, 10)
    while other == digit:
        other = source.randrange(0, 10)
    return other


def _selection_count(option_slug: str) -> int:
    if option_slug == "one-pop":
        return 1
    match = re.match(r"^(\d+)-", option_slug)
    if match is None:
        return 0
    return int(match.group(1))
