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

_OFFICIAL_NATIONAL_RESULTS_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

_OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS = {
    "dc",
    "ks",
    "nc",
    "nd",
    "nh",
    "nj",
    "nm",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "vt",
    "va",
    "wv",
    "wi",
    "wy",
}

_NATIONAL_DRAW_DATE_RE = re.compile(
    r"^(Sun|Mon|Tue|Wed|Thu|Fri|Sat),\s+"
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"
)

def parse_official_national_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _OFFICIAL_NATIONAL_RESULTS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        match = _NATIONAL_DRAW_DATE_RE.match(lines[index])
        if match is None:
            index += 1
            continue

        numbers = _national_result_numbers(lines[index][match.end() :])
        cursor = index + 1
        while cursor < len(lines) and len(numbers) < 6:
            if _NATIONAL_DRAW_DATE_RE.match(lines[cursor]) is not None:
                break
            numbers.extend(_national_result_numbers(lines[cursor]))
            cursor += 1
        if len(numbers) >= 6:
            draws.append(
                ParsedDraw(
                    draw_date=_national_draw_date(match),
                    winning_number=", ".join(
                        (
                            *numbers[:5],
                            f"{numbers[5]} {special_number_name}",
                        )
                    ),
                    prizes=(),
                )
            )
        index = max(cursor, index + 1)
    return tuple(draws)

def _national_result_numbers(value: str) -> list[str]:
    return re.findall(r"\b\d{1,2}\b", value)

def _national_draw_date(match: re.Match[str]) -> str:
    raw_date = f"{match.group(1)}, {match.group(2)} {match.group(3)}, {match.group(4)}"
    for date_format in ("%a, %B %d, %Y", "%a, %b %d, %Y"):
        try:
            return datetime.strptime(raw_date, date_format).strftime(_DRAW_DATE_FORMAT)
        except ValueError:
            pass
    raise ValueError(f"invalid draw date: {raw_date}")
