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

_IDAHO_DRAW_PAGE_GAMES = {
    "idaho-cash": (5, None),
    "idaho-pick-3": (3, None),
    "idaho-pick-4": (4, None),
    "lotto-america": (5, "Star Ball"),
    "mega-millions": (5, "Mega Ball"),
    "millionaire-for-life": (5, "Life Ball"),
    "powerball": (5, "Powerball"),
}

_IDAHO_HISTORY_SLUGS = {
    "idaho-pick-3": "pick-3",
    "idaho-pick-4": "pick-4",
    "millionaire-for-life": "millionaire-life",
}

def parse_idaho_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    primary_count, special_number_name = _IDAHO_DRAW_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    draws.extend(
        _parse_idaho_history_rows(
            soup,
            primary_count=primary_count,
            special_number_name=special_number_name,
        )
    )
    for row in soup.select("tr"):
        date_cell = row.find("td", attrs={"data-title": "Date"})
        numbers_cell = row.find("td", attrs={"data-title": "Winning Numbers"})
        if date_cell is None or numbers_cell is None:
            continue
        draw_date = _idaho_draw_date(date_cell.get_text(" ", strip=True))
        numbers = [
            item.get_text(" ", strip=True)
            for item in numbers_cell.select("li")
        ]
        if draw_date is None or len(numbers) < primary_count:
            continue
        primary_numbers = [
            number
            for number in numbers[:primary_count]
            if re.fullmatch(r"\d{1,2}", number)
        ]
        if len(primary_numbers) != primary_count:
            continue
        winning_numbers = primary_numbers
        if special_number_name is not None:
            if len(numbers) < primary_count + 1:
                continue
            special_number = numbers[primary_count]
            if not re.fullmatch(r"\d{1,2}", special_number):
                continue
            winning_numbers = [*primary_numbers, f"{special_number} {special_number_name}"]
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_numbers),
                prizes=(),
            )
        )
    return tuple(draws)

def _parse_idaho_history_rows(
    soup: BeautifulSoup,
    *,
    primary_count: int,
    special_number_name: str | None,
) -> list[ParsedDraw]:
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        draw_date = _idaho_history_draw_date(cells[0].get_text(" ", strip=True))
        if draw_date is None:
            continue
        numbers = re.findall(r"\d+", cells[1].get_text(" ", strip=True))
        if len(numbers) < primary_count:
            continue
        primary_numbers = numbers[:primary_count]
        winning_numbers = primary_numbers
        if special_number_name is not None:
            if len(numbers) < primary_count + 1:
                continue
            winning_numbers = [
                *primary_numbers,
                f"{numbers[primary_count]} {special_number_name}",
            ]
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_numbers),
                prizes=(),
            )
        )
    return draws

def _idaho_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _idaho_history_draw_date(raw_value: str) -> str | None:
    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})(?:\s+(Day|Night))?",
        raw_value,
    )
    if match is None:
        return None
    try:
        draw_date = datetime.strptime(match.group(1), "%Y-%m-%d").strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None
    session = match.group(2)
    if session is not None:
        return f"{draw_date} {session}"
    return draw_date

def _idaho_history_url(game: GameMetadata) -> str:
    history_slug = _IDAHO_HISTORY_SLUGS.get(game.slug, game.slug)
    return urljoin(game.source_url, f"/drawgame/history/{history_slug}")
