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

_ILLINOIS_RESULTS_PAGE_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

def parse_illinois_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ILLINOIS_RESULTS_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for item in soup.select("li"):
        draw = _parse_illinois_result_line(
            item.get_text(" ", strip=True),
            special_number_name,
        )
        if draw is not None:
            draws.append(draw)
    return tuple(draws)

def _parse_illinois_result_line(
    line: str,
    special_number_name: str,
) -> ParsedDraw | None:
    match = re.search(
        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\b",
        line,
    )
    if match is None:
        return None
    numbers = re.findall(r"\b\d{1,2}\b", line[match.end() :])
    if len(numbers) < 6:
        return None
    draw_date = _illinois_draw_date(match.group(0))
    if draw_date is None:
        return None
    return ParsedDraw(
        draw_date=draw_date,
        winning_number=", ".join(
            [*numbers[:5], f"{numbers[5]} {special_number_name}"]
        ),
        prizes=(),
    )

def _illinois_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A %B %d, %Y").strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None
