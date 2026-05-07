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

_LOUISIANA_LATEST_DRAW_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

def parse_louisiana_latest_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _LOUISIANA_LATEST_DRAW_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    content = soup.select_one("main") or soup
    date_match = re.search(
        r"View Latest Draw:\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
        content.get_text(" ", strip=True),
    )
    numbers = [
        item.get_text(" ", strip=True)
        for item in content.select("li")
        if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
    ][:6]
    if date_match is None or len(numbers) != 6:
        return ()
    draw_date = _louisiana_draw_date(date_match.group(1))
    if draw_date is None:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*numbers[:5], f"{numbers[5]} {special_number_name}"]
            ),
            prizes=(),
        ),
    )

def _louisiana_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%B %d, %Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
