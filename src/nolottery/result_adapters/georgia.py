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

_GEORGIA_DRAW_GAMES = {
    "mega-millions": ("MEGA MILLIONS", "MB", "Mega Ball"),
    "powerball": ("POWERBALL", "PB", "Powerball"),
}

_GEORGIA_TIMEZONE = ZoneInfo("America/New_York")

def parse_georgia_draw_games_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_name, special_prefix, special_number_name = _GEORGIA_DRAW_GAMES[game_slug]
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("draws") or ():
        if item.get("gameName") != game_name:
            continue
        if item.get("status") == "OPEN":
            continue
        draw_date = _georgia_draw_date(item.get("closeTime"))
        numbers = _georgia_draw_numbers(item, special_prefix, special_number_name)
        if draw_date is None or numbers is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)

def _georgia_draw_numbers(
    item: dict[str, object],
    special_prefix: str,
    special_number_name: str,
) -> tuple[str, ...] | None:
    results = item.get("results")
    if not isinstance(results, list) or not results:
        return None
    first_result = results[0]
    if not isinstance(first_result, dict):
        return None
    raw_numbers = first_result.get("primary")
    if not isinstance(raw_numbers, list):
        return None
    primary_numbers = [
        str(number)
        for number in raw_numbers
        if isinstance(number, str) and re.fullmatch(r"\d{1,2}", number)
    ][:5]
    special_marker = next(
        (
            number
            for number in raw_numbers
            if isinstance(number, str) and number.startswith(f"{special_prefix}-")
        ),
        None,
    )
    if len(primary_numbers) != 5 or special_marker is None:
        return None
    special_number = special_marker.split("-", 1)[1]
    if not re.fullmatch(r"\d{1,2}", special_number):
        return None
    return (*primary_numbers, f"{special_number} {special_number_name}")

def _georgia_draw_date(raw_value: object) -> str | None:
    milliseconds = _int_value(raw_value)
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=UTC,
    ).astimezone(_GEORGIA_TIMEZONE).strftime(_DRAW_DATE_FORMAT)

def _georgia_draw_games_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ga-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_name, _, _ = _GEORGIA_DRAW_GAMES[game.slug]
    query = urlencode(
        {
            "game-names": game_name,
            "previous-draws": "180",
            "page": "0",
            "size": "180",
        }
    )
    source_url = f"https://www.galottery.com/api/v2/draw-games/draws/page?{query}"
    response = httpx.get(source_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text, str(response.url)
