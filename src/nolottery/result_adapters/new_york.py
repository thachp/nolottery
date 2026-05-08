from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode

from nolottery.fetch_models import ParsedDraw
from nolottery.metadata import GameMetadata
from nolottery.result_adapters.common import (
    AdapterFetch,
    SourceReader,
    SourceSnapshot,
    _DRAW_DATE_FORMAT,
)

_NEW_YORK_OPEN_DATA_LIMIT = 50000
_NEW_YORK_DATASETS = {
    "powerball": "d6yy-54nr",
    "mega-millions": "5xaw-6ayf",
    "new-york-lotto": "6nbc-h7bj",
    "millionaire-for-life": "a4w9-a3tp",
    "numbers": "hsys-3def",
    "win-4": "hsys-3def",
    "take-5": "dg63-4siq",
    "quick-draw": "7sqk-ycpk",
    "pick-10": "bycu-cw7c",
}
_NEW_YORK_OPEN_DATA_GAMES = frozenset(_NEW_YORK_DATASETS)
_NEW_YORK_DAILY_GAMES = {"numbers", "win-4"}
_NEW_YORK_DAILY_NUMBERS_URL = (
    "https://data.ny.gov/resource/hsys-3def.json?"
    f"{urlencode({'$order': 'draw_date DESC', '$limit': _NEW_YORK_OPEN_DATA_LIMIT})}"
)


def parse_new_york_daily_numbers_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    payload = json.loads(raw_json)
    field_names = (
        ("midday_daily", "evening_daily")
        if game_slug == "numbers"
        else ("midday_win_4", "evening_win_4")
    )
    draws: list[ParsedDraw] = []
    for item in payload:
        draw_date = _new_york_draw_date(item.get("draw_date"))
        if draw_date is None:
            continue
        for field_name, session in zip(field_names, ("Midday", "Evening"), strict=True):
            number = item.get(field_name)
            if isinstance(number, str) and number.strip():
                draws.append(
                    ParsedDraw(
                        draw_date=f"{draw_date} {session}",
                        winning_number=number.strip(),
                        prizes=(),
                    )
                )
    return tuple(draws)


def parse_new_york_open_data_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if game_slug in _NEW_YORK_DAILY_GAMES:
        return parse_new_york_daily_numbers_json(raw_json, game_slug)

    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload:
        draw_date = _new_york_draw_date(item.get("draw_date"))
        if draw_date is None:
            continue
        if game_slug == "take-5":
            draws.extend(_new_york_take_5_draws(item, draw_date))
            continue
        winning_number = _new_york_winning_number(item, game_slug)
        if winning_number is None:
            continue
        draw_time = _quick_draw_time(item) if game_slug == "quick-draw" else None
        draws.append(
            ParsedDraw(
                draw_date=f"{draw_date} {draw_time}" if draw_time else draw_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
    return tuple(draws)


def fetch_new_york_open_data_result(
    game: GameMetadata,
    source_dir,
    read_source: SourceReader,
    *,
    backfill: bool = False,
) -> AdapterFetch:
    if source_dir is not None:
        return _new_york_fixture_fetch(game, source_dir, read_source, backfill=backfill)
    if not backfill:
        raw_json, source_url = read_source(
            _new_york_open_data_url(game.slug, limit=_NEW_YORK_OPEN_DATA_LIMIT),
            None,
            f"{game.slug}-ny-backfill",
            suffix=".json",
        )
        draws = parse_new_york_open_data_json(raw_json, game.slug)
        return _new_york_adapter_fetch(source_url, raw_json, draws)
    return _new_york_paginated_backfill(game, read_source)


def _new_york_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    return datetime.fromisoformat(raw_value).strftime(_DRAW_DATE_FORMAT)


def _new_york_open_data_url(
    game_slug: str,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> str:
    query: dict[str, object] = {"$order": "draw_date DESC"}
    if limit is not None:
        query["$limit"] = limit
    if offset:
        query["$offset"] = offset
    return (
        f"https://data.ny.gov/resource/{_NEW_YORK_DATASETS[game_slug]}.json?"
        f"{urlencode(query)}"
    )


def _new_york_fixture_fetch(
    game: GameMetadata,
    source_dir,
    read_source: SourceReader,
    *,
    backfill: bool,
) -> AdapterFetch:
    source_name = f"{game.slug}-ny-backfill"
    first_page = source_dir / f"{source_name}-1.json"
    if not backfill or not first_page.exists():
        raw_json, source_url = read_source(
            _new_york_open_data_url(game.slug, limit=_NEW_YORK_OPEN_DATA_LIMIT),
            source_dir,
            source_name,
            suffix=".json",
        )
        draws = parse_new_york_open_data_json(raw_json, game.slug)
        return _new_york_adapter_fetch(source_url, raw_json, draws)

    page = 1
    all_draws: list[ParsedDraw] = []
    snapshots: list[SourceSnapshot] = []
    while (source_dir / f"{source_name}-{page}.json").exists():
        raw_json, source_url = read_source(
            _new_york_open_data_url(
                game.slug,
                limit=_NEW_YORK_OPEN_DATA_LIMIT,
                offset=(page - 1) * _NEW_YORK_OPEN_DATA_LIMIT,
            ),
            source_dir,
            f"{source_name}-{page}",
            suffix=".json",
        )
        draws = parse_new_york_open_data_json(raw_json, game.slug)
        all_draws.extend(draws)
        snapshots.append(SourceSnapshot(source_url, raw_json, draws))
        page += 1
    return AdapterFetch(
        source_url=snapshots[0].source_url,
        draws=tuple(all_draws),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def _new_york_paginated_backfill(
    game: GameMetadata,
    read_source: SourceReader,
) -> AdapterFetch:
    page = 0
    all_draws: list[ParsedDraw] = []
    snapshots: list[SourceSnapshot] = []
    while True:
        raw_json, source_url = read_source(
            _new_york_open_data_url(
                game.slug,
                limit=_NEW_YORK_OPEN_DATA_LIMIT,
                offset=page * _NEW_YORK_OPEN_DATA_LIMIT,
            ),
            None,
            f"{game.slug}-ny-backfill-{page + 1}",
            suffix=".json",
        )
        draws = parse_new_york_open_data_json(raw_json, game.slug)
        all_draws.extend(draws)
        snapshots.append(SourceSnapshot(source_url, raw_json, draws))
        if len(json.loads(raw_json)) < _NEW_YORK_OPEN_DATA_LIMIT:
            break
        page += 1
    return AdapterFetch(
        source_url=_new_york_open_data_url(game.slug, limit=_NEW_YORK_OPEN_DATA_LIMIT),
        draws=tuple(all_draws),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def _new_york_adapter_fetch(
    source_url: str,
    raw_json: str,
    draws: tuple[ParsedDraw, ...],
) -> AdapterFetch:
    return AdapterFetch(
        source_url=source_url,
        draws=draws,
        snapshots=(SourceSnapshot(source_url, raw_json, draws),),
        page_count=1,
    )


def _new_york_take_5_draws(
    item: dict[str, object],
    draw_date: str,
) -> tuple[ParsedDraw, ...]:
    draws: list[ParsedDraw] = []
    for field_name, session in (
        ("midday_winning_numbers", "Midday"),
        ("evening_winning_numbers", "Evening"),
    ):
        numbers = _space_separated_numbers(item.get(field_name))
        if numbers:
            draws.append(
                ParsedDraw(
                    draw_date=f"{draw_date} {session}",
                    winning_number=", ".join(numbers),
                    prizes=(),
                )
            )
    return tuple(draws)


def _new_york_winning_number(
    item: dict[str, object],
    game_slug: str,
) -> str | None:
    numbers = _space_separated_numbers(item.get("winning_numbers"))
    if not numbers:
        return None
    if game_slug == "powerball":
        if len(numbers) != 6:
            return None
        return ", ".join((*numbers[:5], f"{numbers[5]} Powerball"))
    if game_slug == "mega-millions":
        mega_ball = _single_number(item.get("mega_ball"))
        if len(numbers) != 5 or mega_ball is None:
            return None
        return ", ".join((*numbers, f"{mega_ball} Mega Ball"))
    if game_slug == "millionaire-for-life":
        life_ball = _single_number(item.get("mill_ball"))
        if len(numbers) != 5 or life_ball is None:
            return None
        return ", ".join((*numbers, f"{life_ball} Life Ball"))
    if game_slug == "new-york-lotto":
        bonus = _single_number(item.get("bonus"))
        if len(numbers) != 6:
            return None
        return ", ".join((*numbers, f"{bonus} Bonus")) if bonus else ", ".join(numbers)
    return ", ".join(numbers)


def _space_separated_numbers(raw_value: object) -> tuple[str, ...]:
    if not isinstance(raw_value, str):
        return ()
    return tuple(raw_value.split())


def _single_number(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None
    return raw_value.strip()


def _quick_draw_time(item: dict[str, object]) -> str | None:
    raw_time = item.get("draw_time")
    if not isinstance(raw_time, str) or not raw_time:
        return None
    return raw_time
