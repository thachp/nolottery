from __future__ import annotations

import random
import re
import sqlite3
from dataclasses import dataclass
from statistics import mean

from .audit import Draw, load_valid_draws
from .metadata import GameMetadata, WagerOption
from .number_format import quick_pick
from .recommend import format_number_label


METHOD = "low-share-heuristic-no-odds-edge"


@dataclass(frozen=True)
class LowSharePick:
    numbers: tuple[int, ...]
    label: str
    low_share_score: int
    reasons: tuple[str, ...]
    method: str = METHOD


@dataclass(frozen=True)
class LowShareOptionResult:
    game_slug: str
    game_name: str
    option_slug: str
    option_label: str
    picks: tuple[LowSharePick, ...]
    warnings: tuple[str, ...]


def generate_low_share_options(
    conn: sqlite3.Connection,
    game: GameMetadata,
    *,
    count: int = 5,
    candidates: int = 1000,
    seed: int | None = None,
    avoid_recent_winning_combos: bool = False,
    last: int | None = None,
) -> tuple[LowShareOptionResult, ...]:
    if candidates < count:
        raise ValueError("candidates must be greater than or equal to count")
    rng = random.Random(seed) if seed is not None else random.SystemRandom()
    recent_draws: tuple[Draw, ...] = ()
    recent_warnings: tuple[str, ...] = ()
    if avoid_recent_winning_combos:
        recent_draws, recent_warnings = load_valid_draws(conn, game.slug, last=last)

    return tuple(
        _generate_option(
            rng,
            game,
            option,
            count=count,
            candidates=candidates,
            recent_draws=recent_draws,
            recent_warnings=recent_warnings,
            avoid_recent_winning_combos=avoid_recent_winning_combos,
        )
        for option in game.wager_options
    )


def _generate_option(
    rng,
    game: GameMetadata,
    option: WagerOption,
    *,
    count: int,
    candidates: int,
    recent_draws: tuple[Draw, ...],
    recent_warnings: tuple[str, ...],
    avoid_recent_winning_combos: bool,
) -> LowShareOptionResult:
    recent_keys = _recent_keys(game.slug, option.slug, recent_draws)
    warnings = list(recent_warnings)
    if avoid_recent_winning_combos and not recent_draws:
        warnings.append(
            "no stored draw data was available for --avoid-recent-winning-combos"
        )

    scored: dict[tuple[int, ...], LowSharePick] = {}
    for _ in range(candidates):
        numbers = _candidate_numbers(rng, game.slug, option.slug)
        if _candidate_matches_recent(game.slug, option.slug, numbers, recent_keys):
            continue
        if numbers in scored:
            continue
        score, reasons = _score_numbers(game.slug, option.slug, numbers)
        scored[numbers] = LowSharePick(
            numbers=numbers,
            label=format_number_label(game.slug, option.slug, numbers),
            low_share_score=score,
            reasons=reasons,
        )

    picks = tuple(
        sorted(
            scored.values(),
            key=lambda pick: pick.low_share_score,
            reverse=True,
        )[:count]
    )
    if len(picks) < count:
        warnings.append(
            f"requested {count} picks but only {len(picks)} unique candidates were available"
        )
    return LowShareOptionResult(
        game_slug=game.slug,
        game_name=game.name,
        option_slug=option.slug,
        option_label=option.label,
        picks=picks,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _candidate_numbers(rng, game_slug: str, option_slug: str) -> tuple[int, ...]:
    if game_slug in {"cashpop", "oregon-cash-pop"}:
        return tuple(sorted(rng.sample(range(1, 16), _selection_count(option_slug))))
    if game_slug in {"daily-keno", "oregon-keno"}:
        return tuple(sorted(rng.sample(range(1, 81), _selection_count(option_slug))))
    if game_slug == "hot-spot":
        return tuple(sorted(rng.sample(range(1, 81), _selection_count(option_slug))))
    if game_slug == "powerball":
        return (*sorted(rng.sample(range(1, 70), 5)), rng.randrange(1, 27))
    if game_slug == "mega-millions":
        return (*sorted(rng.sample(range(1, 71), 5)), rng.randrange(1, 25))
    if game_slug == "lotto":
        return (
            *sorted(rng.sample(range(1, 50), 6)),
            *sorted(rng.sample(range(1, 50), 6)),
        )
    if game_slug == "hit-5":
        return tuple(sorted(rng.sample(range(1, 43), 5)))
    if game_slug == "match-4":
        return tuple(sorted(rng.sample(range(1, 25), 4)))
    if game_slug == "pick-3":
        return _pick3_candidate(rng, option_slug)
    try:
        return quick_pick(game_slug, option_slug, rng=rng)
    except ValueError as exc:
        raise ValueError(f"unknown game: {game_slug}") from exc


def _pick3_candidate(rng, option_slug: str) -> tuple[int, ...]:
    if "pair" in option_slug:
        return (rng.randrange(0, 10), rng.randrange(0, 10))
    if "-6-way" in option_slug:
        return tuple(rng.sample(range(0, 10), 3))
    if "-3-way" in option_slug:
        digit = rng.randrange(0, 10)
        other = rng.randrange(0, 10)
        while other == digit:
            other = rng.randrange(0, 10)
        numbers = [digit, digit, other]
        rng.shuffle(numbers)
        return tuple(numbers)
    return tuple(rng.randrange(0, 10) for _ in range(3))


def _score_numbers(
    game_slug: str,
    option_slug: str,
    numbers: tuple[int, ...],
) -> tuple[int, tuple[str, ...]]:
    if game_slug == "lotto":
        scored_plays = [
            _score_play(game_slug, numbers[:6]),
            _score_play(game_slug, numbers[6:]),
        ]
        score = round(mean(result[0] for result in scored_plays))
        reasons = _merge_reasons(*(result[1] for result in scored_plays))
        return score, reasons
    if game_slug == "powerball":
        return _score_play(game_slug, numbers[:5], bonus=numbers[5])
    if game_slug == "mega-millions":
        return _score_play(game_slug, numbers[:5], bonus=numbers[5])
    if game_slug == "lotto-america":
        return _score_play(game_slug, numbers[:5], bonus=numbers[5])
    if game_slug == "millionaire-for-life":
        return _score_play(game_slug, numbers[:5], bonus=numbers[5])
    if game_slug == "superlotto-plus":
        return _score_play(game_slug, numbers[:5], bonus=numbers[5])
    if game_slug == "pick-3":
        return _score_pick3(option_slug, numbers)
    if game_slug == "daily-derby":
        return _score_play(game_slug, numbers[:3])
    return _score_play(game_slug, numbers)


def _score_play(
    game_slug: str,
    numbers: tuple[int, ...],
    *,
    bonus: int | None = None,
) -> tuple[int, tuple[str, ...]]:
    score = 100
    reasons: list[str] = []

    birthday_count = sum(1 for number in numbers if 1 <= number <= 31)
    if len(numbers) >= 4 and birthday_count >= len(numbers) - 1:
        score -= 22
    elif len(numbers) >= 4 and birthday_count <= len(numbers) - 2:
        reasons.append("few birthday-range numbers")
    elif len(numbers) <= 3 and birthday_count == len(numbers):
        score -= 8

    longest_run = _longest_sequential_run(numbers)
    if longest_run >= 3:
        score -= 18
    else:
        reasons.append("no sequential run")

    spread = max(numbers) - min(numbers) if len(numbers) > 1 else 0
    target_spread = _target_spread(game_slug)
    if len(numbers) > 2 and spread < target_spread:
        score -= 14
    elif len(numbers) > 1:
        reasons.append("wide spread")

    if _is_arithmetic_pattern(numbers):
        score -= 16
    else:
        reasons.append("no arithmetic pattern")

    popular_count = sum(1 for number in numbers if number in {7, 11, 13, 21, 23})
    if popular_count >= 2:
        score -= 12
    elif popular_count == 0:
        reasons.append("avoids popular numbers")

    if bonus is not None and bonus in {7, 13, 21, 23}:
        score -= 4
    elif bonus is not None:
        reasons.append("bonus ball avoids popular numbers")

    return max(0, min(100, score)), _merge_reasons(tuple(reasons))


def _score_pick3(
    option_slug: str,
    numbers: tuple[int, ...],
) -> tuple[int, tuple[str, ...]]:
    score = 100
    reasons: list[str] = []
    if len(set(numbers)) == 1:
        score -= 35
    elif len(set(numbers)) == len(numbers):
        reasons.append("no repeated digits")

    if tuple(numbers) in {
        (0, 0, 0),
        (1, 2, 3),
        (3, 2, 1),
        (7, 7, 7),
        (8, 8, 8),
        (9, 9, 9),
    }:
        score -= 30
    else:
        reasons.append("avoids obvious digit pattern")

    if len(numbers) == 3 and numbers[0] == numbers[2]:
        score -= 15
    elif len(numbers) == 3:
        reasons.append("not a palindrome")

    if any(number in {7, 3, 0} for number in numbers):
        score -= 6
    else:
        reasons.append("avoids common lucky digits")

    if "-3-way" in option_slug and len(set(numbers)) == 2:
        reasons.append("valid 3-way shape")
    if "-6-way" in option_slug and len(set(numbers)) == 3:
        reasons.append("valid 6-way shape")
    if "pair" in option_slug:
        reasons.append("pair wager shape")
    return max(0, min(100, score)), _merge_reasons(tuple(reasons))


def _recent_keys(
    game_slug: str,
    option_slug: str,
    recent_draws: tuple[Draw, ...],
) -> set[tuple[int, ...]]:
    return {
        key
        for draw in recent_draws
        if (key := _draw_key(game_slug, option_slug, draw)) is not None
    }


def _candidate_matches_recent(
    game_slug: str,
    option_slug: str,
    numbers: tuple[int, ...],
    recent_keys: set[tuple[int, ...]],
) -> bool:
    if not recent_keys:
        return False
    if game_slug == "lotto":
        return numbers[:6] in recent_keys or numbers[6:] in recent_keys
    return _candidate_key(game_slug, option_slug, numbers) in recent_keys


def _draw_key(
    game_slug: str,
    option_slug: str,
    draw: Draw,
) -> tuple[int, ...] | None:
    if game_slug == "pick-3":
        digits = (
            draw.pools["position_1"][0],
            draw.pools["position_2"][0],
            draw.pools["position_3"][0],
        )
        if "front-pair" in option_slug:
            return digits[:2]
        if "back-pair" in option_slug:
            return digits[1:]
        if "box" in option_slug or "superbox" in option_slug:
            return tuple(sorted(digits))
        return digits
    if game_slug in {
        "powerball",
        "mega-millions",
        "superlotto-plus",
        "lotto-america",
        "millionaire-for-life",
    }:
        first_pool, second_pool = tuple(draw.pools)
        return (*tuple(sorted(draw.pools[first_pool])), draw.pools[second_pool][0])
    if game_slug == "daily-derby":
        return (
            draw.pools["first"][0],
            draw.pools["second"][0],
            draw.pools["third"][0],
        )
    return tuple(sorted(next(iter(draw.pools.values()))))


def _candidate_key(
    game_slug: str,
    option_slug: str,
    numbers: tuple[int, ...],
) -> tuple[int, ...]:
    if game_slug == "pick-3" and ("box" in option_slug or "superbox" in option_slug):
        return tuple(sorted(numbers))
    return numbers


def _selection_count(option_slug: str) -> int:
    if option_slug == "one-pop":
        return 1
    match = re.match(r"^(\d+)-", option_slug)
    if match is None:
        raise ValueError(f"cannot infer selection count from {option_slug}")
    return int(match.group(1))


def _longest_sequential_run(numbers: tuple[int, ...]) -> int:
    ordered = sorted(numbers)
    longest = current = 1 if ordered else 0
    for previous, number in zip(ordered, ordered[1:]):
        if number == previous + 1:
            current += 1
            longest = max(longest, current)
        else:
            current = 1
    return longest


def _is_arithmetic_pattern(numbers: tuple[int, ...]) -> bool:
    ordered = sorted(numbers)
    if len(ordered) < 3:
        return False
    gaps = {number - previous for previous, number in zip(ordered, ordered[1:])}
    return len(gaps) == 1


def _target_spread(game_slug: str) -> int:
    return {
        "cashpop": 6,
        "daily-keno": 25,
        "hot-spot": 25,
        "hit-5": 16,
        "lotto": 20,
        "match-4": 8,
        "mega-millions": 24,
        "lotto-america": 18,
        "millionaire-for-life": 20,
        "oregon-cash-pop": 6,
        "oregon-keno": 25,
        "oregon-megabucks": 18,
        "oregon-win-for-life": 25,
        "powerball": 24,
        "superlotto-plus": 18,
        "fantasy-5": 14,
    }.get(game_slug, 0)


def _merge_reasons(*groups: tuple[str, ...]) -> tuple[str, ...]:
    reasons: list[str] = []
    for group in groups:
        for reason in group:
            if reason not in reasons:
                reasons.append(reason)
    return tuple(reasons)
