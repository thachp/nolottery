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

_IOWA_WINNING_NUMBERS_GAMES = {
    "mega-millions": (1, "Mega Ball"),
    "powerball": (0, "Powerball"),
}

def parse_iowa_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    draw_index, special_number_name = _IOWA_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    matches = tuple(
        re.finditer(
            r"Drawing Date:\s*(\d{1,2})/(\d{1,2}):\s*"
            r"(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*"
            r"(\d{1,2})\s*-\s*(\d{1,2})\s+(\d{1,2})",
            text,
        )
    )
    if draw_index >= len(matches):
        return ()
    match = matches[draw_index]
    draw_date = _iowa_draw_date(match.group(1), match.group(2))
    if draw_date is None:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [
                    match.group(3),
                    match.group(4),
                    match.group(5),
                    match.group(6),
                    match.group(7),
                    f"{match.group(8)} {special_number_name}",
                ]
            ),
            prizes=(),
        ),
    )

def _iowa_draw_date(raw_month: str, raw_day: str) -> str | None:
    try:
        return datetime(
            date.today().year,
            int(raw_month),
            int(raw_day),
        ).strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
