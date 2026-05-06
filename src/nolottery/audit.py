from __future__ import annotations

import re
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations, product
from math import comb
from statistics import mean
from typing import Literal

from scipy.stats import chisquare


Status = Literal["OK", "WARN", "INSUFFICIENT_DATA", "NOT_APPLICABLE"]
_DRAW_DATE_FORMAT = "%a, %b %d, %Y"
_MIN_EXPECTED = 5.0
_WARN_P_VALUE = 0.01


@dataclass(frozen=True)
class AuditPool:
    name: str
    minimum: int
    maximum: int
    draw_size: int
    ordered: bool = False

    @property
    def values(self) -> tuple[int, ...]:
        return tuple(range(self.minimum, self.maximum + 1))

    @property
    def bucket_count(self) -> int:
        if self.ordered:
            return len(self.values)
        return self.maximum - self.minimum + 1


@dataclass(frozen=True)
class AuditRule:
    game_slug: str
    pools: tuple[AuditPool, ...]


@dataclass(frozen=True)
class Draw:
    draw_date: str
    sort_key: tuple[int, str]
    pools: dict[str, tuple[int, ...]]


AUDIT_RULES: dict[str, AuditRule] = {
    "cashpop": AuditRule(
        game_slug="cashpop",
        pools=(AuditPool("numbers", 1, 15, 1),),
    ),
    "daily-keno": AuditRule(
        game_slug="daily-keno",
        pools=(AuditPool("numbers", 1, 80, 20),),
    ),
    "hit-5": AuditRule(
        game_slug="hit-5",
        pools=(AuditPool("numbers", 1, 42, 5),),
    ),
    "lotto": AuditRule(
        game_slug="lotto",
        pools=(AuditPool("numbers", 1, 49, 6),),
    ),
    "match-4": AuditRule(
        game_slug="match-4",
        pools=(AuditPool("numbers", 1, 24, 4),),
    ),
    "mega-millions": AuditRule(
        game_slug="mega-millions",
        pools=(
            AuditPool("white", 1, 70, 5),
            AuditPool("mega_ball", 1, 24, 1),
        ),
    ),
    "pick-3": AuditRule(
        game_slug="pick-3",
        pools=(
            AuditPool("position_1", 0, 9, 1, ordered=True),
            AuditPool("position_2", 0, 9, 1, ordered=True),
            AuditPool("position_3", 0, 9, 1, ordered=True),
        ),
    ),
    "powerball": AuditRule(
        game_slug="powerball",
        pools=(
            AuditPool("white", 1, 69, 5),
            AuditPool("powerball", 1, 26, 1),
        ),
    ),
}


def frequency_audit(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    last: int | None = None,
) -> list[dict[str, object]]:
    draws, warnings = load_valid_draws(conn, game_slug, last=last)
    rule = _rule_for(game_slug)
    return [
        _frequency_result(game_slug, pool, draws, warnings)
        for pool in rule.pools
    ]


def chi_square_audit(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    last: int | None = None,
) -> list[dict[str, object]]:
    results = frequency_audit(conn, game_slug, last=last)
    for result in results:
        result["test"] = "chi-square"
    return results


def combination_audit(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    size: int,
    last: int | None = None,
) -> list[dict[str, object]]:
    draws, warnings = load_valid_draws(conn, game_slug, last=last)
    rule = _rule_for(game_slug)
    if rule.game_slug == "pick-3":
        return _pick3_combination_audit(game_slug, size, draws, warnings)
    return [
        _combination_result(game_slug, pool, draws, warnings, size)
        for pool in rule.pools
    ]


def gap_audit(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    last: int | None = None,
) -> list[dict[str, object]]:
    draws, warnings = load_valid_draws(conn, game_slug, last=last)
    rule = _rule_for(game_slug)
    return [_gap_result(game_slug, pool, draws, warnings) for pool in rule.pools]


def load_valid_draws(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    last: int | None = None,
) -> tuple[tuple[Draw, ...], tuple[str, ...]]:
    rule = _rule_for(game_slug)
    warnings: list[str] = []
    draws: list[Draw] = []
    skipped = 0
    for draw_date, winning_number in _stored_draw_rows(conn, game_slug):
        draw = _parse_draw(rule, draw_date, winning_number)
        if draw is None:
            skipped += 1
            continue
        draws.append(draw)

    draws.sort(key=lambda draw: draw.sort_key)
    if skipped:
        warnings.append(
            f"{skipped} draws had unparseable or invalid winning_number values"
        )
    unparsed_dates = sum(1 for draw in draws if draw.sort_key[0] == 1)
    if unparsed_dates:
        warnings.append(f"{unparsed_dates} draws had unparseable draw_date values")
    if last is not None:
        draws = draws[-last:]
    return tuple(draws), tuple(warnings)


def _frequency_result(
    game_slug: str,
    pool: AuditPool,
    draws: tuple[Draw, ...],
    warnings: tuple[str, ...],
) -> dict[str, object]:
    observed = Counter(
        value
        for draw in draws
        for value in draw.pools.get(pool.name, ())
    )
    expected = len(draws) * pool.draw_size / pool.bucket_count
    buckets = [
        {
            "value": value,
            "observed": observed[value],
            "expected": expected,
            "delta": observed[value] - expected,
            "ratio": (observed[value] / expected if expected else None),
        }
        for value in pool.values
    ]
    statistic, p_value = _chi_square(
        [bucket["observed"] for bucket in buckets],
        expected,
    )
    result_warnings = list(warnings)
    if expected < _MIN_EXPECTED:
        result_warnings.append(f"expected count per bucket {expected:.2f} is below 5")
    return {
        "game_slug": game_slug,
        "pool": pool.name,
        "test": "frequency",
        "draw_count": len(draws),
        "status": _status(expected, p_value),
        "chi_square": statistic,
        "degrees_of_freedom": pool.bucket_count - 1,
        "p_value": p_value,
        "expected_per_bucket": expected,
        "warnings": result_warnings,
        "buckets": buckets,
    }


def _gap_result(
    game_slug: str,
    pool: AuditPool,
    draws: tuple[Draw, ...],
    warnings: tuple[str, ...],
) -> dict[str, object]:
    appearances = Counter(
        value
        for draw in draws
        for value in draw.pools.get(pool.name, ())
    )
    last_seen: dict[int, int] = {}
    completed_gaps: dict[int, list[int]] = {value: [] for value in pool.values}
    pooled_gaps: list[int] = []
    for index, draw in enumerate(draws):
        for value in draw.pools.get(pool.name, ()):
            if value in last_seen:
                gap = index - last_seen[value] - 1
                completed_gaps[value].append(gap)
                pooled_gaps.append(gap)
            last_seen[value] = index

    values = []
    for value in pool.values:
        gaps = completed_gaps[value]
        values.append(
            {
                "value": value,
                "appearances": appearances[value],
                "current_gap": (
                    len(draws) - last_seen[value] - 1
                    if value in last_seen
                    else len(draws)
                ),
                "max_gap": max(gaps) if gaps else None,
                "average_gap": mean(gaps) if gaps else None,
            }
        )

    gap_buckets, min_expected = _gap_buckets(pooled_gaps, pool)
    statistic, p_value = _chi_square_from_buckets(gap_buckets)
    result_warnings = list(warnings)
    if not pooled_gaps:
        result_warnings.append("no completed gaps were available")
    elif min_expected < _MIN_EXPECTED:
        result_warnings.append(
            f"minimum expected gap bucket count {min_expected:.2f} is below 5"
        )
    return {
        "game_slug": game_slug,
        "pool": pool.name,
        "test": "gaps",
        "draw_count": len(draws),
        "status": _status(min_expected, p_value),
        "chi_square": statistic,
        "degrees_of_freedom": (len(gap_buckets) - 1 if gap_buckets else None),
        "p_value": p_value,
        "completed_gap_count": len(pooled_gaps),
        "warnings": result_warnings,
        "values": values,
        "gap_buckets": gap_buckets,
    }


def _gap_buckets(
    pooled_gaps: list[int],
    pool: AuditPool,
) -> tuple[list[dict[str, object]], float]:
    if not pooled_gaps:
        return [], 0.0
    probability = pool.draw_size / pool.bucket_count
    total = len(pooled_gaps)
    max_gap = max(pooled_gaps)
    observed = Counter(pooled_gaps)
    buckets: list[dict[str, object]] = []
    for gap in range(max_gap + 1):
        expected = total * ((1 - probability) ** gap) * probability
        buckets.append(
            {
                "gap": str(gap),
                "observed": observed[gap],
                "expected": expected,
            }
        )
    tail_start = max_gap + 1
    tail_expected = total * ((1 - probability) ** tail_start)
    buckets.append(
        {
            "gap": f">={tail_start}",
            "observed": sum(
                count for gap, count in observed.items() if gap >= tail_start
            ),
            "expected": tail_expected,
        }
    )
    return buckets, min(float(bucket["expected"]) for bucket in buckets)


def _combination_result(
    game_slug: str,
    pool: AuditPool,
    draws: tuple[Draw, ...],
    warnings: tuple[str, ...],
    size: int,
) -> dict[str, object]:
    test_name = "pairs" if size == 2 else "triples"
    if pool.draw_size < size:
        return {
            "game_slug": game_slug,
            "pool": pool.name,
            "test": test_name,
            "draw_count": len(draws),
            "status": "NOT_APPLICABLE",
            "chi_square": None,
            "degrees_of_freedom": None,
            "p_value": None,
            "expected_per_bucket": None,
            "warnings": list(warnings),
            "buckets": [],
        }

    observed = Counter(
        combination
        for draw in draws
        for combination in combinations(sorted(draw.pools.get(pool.name, ())), size)
    )
    universe = tuple(combinations(pool.values, size))
    total_observations = len(draws) * comb(pool.draw_size, size)
    expected = total_observations / len(universe) if universe else 0
    buckets = [
        {
            "combination": list(combination),
            "observed": observed[combination],
            "expected": expected,
            "delta": observed[combination] - expected,
            "ratio": (observed[combination] / expected if expected else None),
        }
        for combination in universe
    ]
    statistic, p_value = _chi_square(
        [bucket["observed"] for bucket in buckets],
        expected,
    )
    result_warnings = list(warnings)
    if expected < _MIN_EXPECTED:
        result_warnings.append(f"expected count per bucket {expected:.2f} is below 5")
    return {
        "game_slug": game_slug,
        "pool": pool.name,
        "test": test_name,
        "draw_count": len(draws),
        "status": _status(expected, p_value),
        "chi_square": statistic,
        "degrees_of_freedom": len(universe) - 1,
        "p_value": p_value,
        "expected_per_bucket": expected,
        "warnings": result_warnings,
        "buckets": buckets,
    }


def _pick3_combination_audit(
    game_slug: str,
    size: int,
    draws: tuple[Draw, ...],
    warnings: tuple[str, ...],
) -> list[dict[str, object]]:
    if size == 2:
        return [
            _ordered_digit_result(game_slug, "front_pair", draws, warnings, (0, 1)),
            _ordered_digit_result(game_slug, "back_pair", draws, warnings, (1, 2)),
        ]
    return [
        _ordered_digit_result(game_slug, "triple", draws, warnings, (0, 1, 2)),
    ]


def _ordered_digit_result(
    game_slug: str,
    pool_name: str,
    draws: tuple[Draw, ...],
    warnings: tuple[str, ...],
    positions: tuple[int, ...],
) -> dict[str, object]:
    test_name = "pairs" if len(positions) == 2 else "triples"
    labels = tuple(
        "".join(str(digit) for digit in digits)
        for digits in product(range(10), repeat=len(positions))
    )
    observed = Counter(
        "".join(
            str(draw.pools[f"position_{position + 1}"][0])
            for position in positions
        )
        for draw in draws
    )
    expected = len(draws) / len(labels) if labels else 0
    buckets = [
        {
            "combination": label,
            "observed": observed[label],
            "expected": expected,
            "delta": observed[label] - expected,
            "ratio": (observed[label] / expected if expected else None),
        }
        for label in labels
    ]
    statistic, p_value = _chi_square(
        [bucket["observed"] for bucket in buckets],
        expected,
    )
    result_warnings = list(warnings)
    if expected < _MIN_EXPECTED:
        result_warnings.append(f"expected count per bucket {expected:.2f} is below 5")
    return {
        "game_slug": game_slug,
        "pool": pool_name,
        "test": test_name,
        "draw_count": len(draws),
        "status": _status(expected, p_value),
        "chi_square": statistic,
        "degrees_of_freedom": len(labels) - 1,
        "p_value": p_value,
        "expected_per_bucket": expected,
        "warnings": result_warnings,
        "buckets": buckets,
    }


def _stored_draw_rows(
    conn: sqlite3.Connection,
    game_slug: str,
) -> tuple[tuple[str, str], ...]:
    rows = conn.execute(
        """
        select min(id) as first_id, draw_date, winning_number
        from draw_results
        where game_slug = ?
        group by draw_date, winning_number
        order by first_id
        """,
        (game_slug,),
    ).fetchall()
    return tuple((row["draw_date"], row["winning_number"]) for row in rows)


def _parse_draw(
    rule: AuditRule,
    draw_date: str,
    winning_number: str,
) -> Draw | None:
    numbers = _parse_numbers(rule.game_slug, winning_number)
    if rule.game_slug == "pick-3":
        if len(numbers) != 3:
            return None
        pools = {
            "position_1": (numbers[0],),
            "position_2": (numbers[1],),
            "position_3": (numbers[2],),
        }
    elif rule.game_slug in {"powerball", "mega-millions"}:
        if len(numbers) != 6:
            return None
        pools = {
            rule.pools[0].name: tuple(numbers[:5]),
            rule.pools[1].name: (numbers[5],),
        }
    else:
        if len(numbers) != rule.pools[0].draw_size:
            return None
        pools = {rule.pools[0].name: tuple(numbers)}

    for pool in rule.pools:
        values = pools[pool.name]
        if any(value < pool.minimum or value > pool.maximum for value in values):
            return None
        if not pool.ordered and len(set(values)) != len(values):
            return None
    return Draw(
        draw_date=draw_date,
        sort_key=_sort_key(draw_date),
        pools=pools,
    )


def _parse_numbers(game_slug: str, winning_number: str) -> tuple[int, ...]:
    tokens = re.findall(r"\d+", winning_number)
    if game_slug == "pick-3" and len(tokens) == 1 and len(tokens[0]) == 3:
        return tuple(int(digit) for digit in tokens[0])
    return tuple(int(token) for token in tokens)


def _sort_key(draw_date: str) -> tuple[int, str]:
    try:
        parsed = datetime.strptime(draw_date, _DRAW_DATE_FORMAT).date()
    except ValueError:
        return (1, draw_date)
    return (0, parsed.isoformat())


def _rule_for(game_slug: str) -> AuditRule:
    try:
        return AUDIT_RULES[game_slug]
    except KeyError as exc:
        raise ValueError(f"unknown game: {game_slug}") from exc


def _chi_square(
    observed: list[int],
    expected: float,
) -> tuple[float | None, float | None]:
    if not observed or expected <= 0:
        return None, None
    expected_values = [expected] * len(observed)
    result = chisquare(observed, expected_values)
    return float(result.statistic), float(result.pvalue)


def _chi_square_from_buckets(
    buckets: list[dict[str, object]],
) -> tuple[float | None, float | None]:
    if len(buckets) < 2:
        return None, None
    observed = [int(bucket["observed"]) for bucket in buckets]
    expected = [float(bucket["expected"]) for bucket in buckets]
    if not expected or sum(expected) <= 0:
        return None, None
    result = chisquare(observed, expected)
    return float(result.statistic), float(result.pvalue)


def _status(expected: float, p_value: float | None) -> Status:
    if expected < _MIN_EXPECTED:
        return "INSUFFICIENT_DATA"
    if p_value is not None and p_value < _WARN_P_VALUE:
        return "WARN"
    return "OK"
