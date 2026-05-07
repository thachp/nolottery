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

_MARYLAND_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}

def parse_maryland_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_label, special_number_name = _MARYLAND_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    heading = soup.find(string=re.compile(rf"^\s*{re.escape(game_label)}\s*$", re.I))
    if heading is None:
        return ()
    table = (
        heading.find_parent().find_next("table")
        if isinstance(heading, NavigableString)
        else None
    )
    if not isinstance(table, Tag):
        return ()
    draws: list[ParsedDraw] = []
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        draw_date = _maryland_draw_date(cells[0].get_text(" ", strip=True))
        primary_numbers = [
            item.get_text(" ", strip=True)
            for item in cells[1].select("li")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        special_numbers = [
            item.get_text(" ", strip=True)
            for item in cells[2].select("li")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        if draw_date is None or len(primary_numbers) != 5 or not special_numbers:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_numbers[0]} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _maryland_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
