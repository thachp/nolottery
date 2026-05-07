from __future__ import annotations

import json
import re
import ssl
from datetime import UTC, date, datetime
from math import ceil
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag

from nolottery.fetch_models import ParsedDraw, PrizeRow
from nolottery.metadata import GameMetadata
from nolottery.result_adapters.common import (
    AdapterFetch,
    SourceReader,
    SourceSnapshot,
    _DRAW_DATE_FORMAT,
    _extract_pdf_text,
    _float_value,
    _int_from_text,
    _int_value,
    _money_to_float,
    _page_lines,
)

_KENTUCKY_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("26", "MEGABALL", "Mega Ball"),
    "powerball": ("12", "POWERBALL", "Powerball"),
}

def parse_kentucky_winning_numbers_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, special_key, special_number_name = _KENTUCKY_WINNING_NUMBERS_GAMES[game_slug]
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("DRAW_HISTORY") or ():
        draw_date = _kentucky_draw_date(item.get("DRAW_DATE"))
        primary_numbers = _kentucky_primary_numbers(item.get("DRAW_VALUES"))
        special_number = _kentucky_special_number(item, special_key)
        if draw_date is None or primary_numbers is None or special_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _kentucky_primary_numbers(raw_values: object) -> tuple[str, ...] | None:
    if not isinstance(raw_values, list):
        return None
    sorted_values = sorted(
        (
            value
            for value in raw_values
            if isinstance(value, dict)
            and _int_value(value.get("DRAW_NUMBER_POSITION")) is not None
            and _int_value(value.get("DRAW_VALUE")) is not None
        ),
        key=lambda value: int(value["DRAW_NUMBER_POSITION"]),
    )
    numbers = tuple(str(int(value["DRAW_VALUE"])) for value in sorted_values[:5])
    if len(numbers) != 5:
        return None
    return numbers

def _kentucky_special_number(item: dict[str, object], special_key: str) -> str | None:
    special_args = item.get("SPECIAL_ARGS")
    if not isinstance(special_args, dict):
        return None
    special_number = _int_value(special_args.get(special_key))
    if special_number is None:
        return None
    return str(special_number)

def _kentucky_draw_date(raw_value: object) -> str | None:
    milliseconds = _int_value(raw_value)
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).strftime(
        _DRAW_DATE_FORMAT
    )

def _kentucky_winning_numbers_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ky-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_number, _, _ = _KENTUCKY_WINNING_NUMBERS_GAMES[game.slug]
    source_url = "https://www.kylottery.com/webhandlers/WinningNumbers.xhtml"
    payload = json.dumps({"gameNumber": game_number, "infoRequest": "11"})
    response = httpx.post(
        source_url,
        content=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)
