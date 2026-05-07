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

_INDIANA_DRAW_PAGE_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

def parse_indiana_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _INDIANA_DRAW_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    section = soup.select_one("section.drawing-numbers")
    if section is None:
        return ()
    date_node = section.select_one(".sub-title")
    numbers_container = section.select_one(".numbers-container")
    if date_node is None or numbers_container is None:
        return ()
    draw_date = _indiana_draw_date(date_node.get_text(" ", strip=True))
    numbers = [
        item.get_text(" ", strip=True)
        for item in numbers_container.select(".winning-number")
    ]
    if draw_date is None or len(numbers) != 6:
        return ()
    primary_numbers = [
        number for number in numbers[:5] if re.fullmatch(r"\d{1,2}", number)
    ]
    special_number = numbers[5]
    if len(primary_numbers) != 5 or not re.fullmatch(r"\d{1,2}", special_number):
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*primary_numbers, f"{special_number} {special_number_name}"]
            ),
            prizes=(),
        ),
    )

def _indiana_draw_date(raw_value: str) -> str | None:
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", raw_value)
    try:
        parsed_date = datetime.strptime(
            f"{cleaned}, {date.today().year}",
            "%A, %B %d, %Y",
        )
    except ValueError:
        return None
    return parsed_date.strftime(_DRAW_DATE_FORMAT)
