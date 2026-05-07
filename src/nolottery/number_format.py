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
    "hit-5": NumberFormat(
        game_slug="hit-5",
        pools=(NumberPool("white", 1, 42, 5),),
    ),
    "match-4": NumberFormat(
        game_slug="match-4",
        pools=(NumberPool("white", 1, 24, 4),),
    ),
}


def quick_pick(
    game_slug: str,
    option_slug: str,
    *,
    rng: RandomSource | None = None,
) -> tuple[int, ...]:
    source = rng if rng is not None else random.SystemRandom()
    if game_slug == "cashpop":
        count = _selection_count(option_slug)
        if count >= 15:
            return tuple(range(1, 16))
        return tuple(sorted(source.sample(range(1, 16), count)))
    if game_slug == "daily-keno":
        return tuple(sorted(source.sample(range(1, 81), _selection_count(option_slug))))
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
