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

_COLORADO_DRAWING_HISTORY_GAMES = {
    "mega-millions": ("Mega Millions Numbers", "Mega Ball"),
    "powerball": ("Powerball Numbers", "Powerball"),
}

def parse_colorado_drawing_history(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    numbers_label, special_number_name = _COLORADO_DRAWING_HISTORY_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        draw_date = _colorado_draw_date(lines[index])
        if draw_date is None:
            index += 1
            continue
        cursor = index + 1
        while cursor < len(lines) and lines[cursor] != numbers_label:
            if _colorado_draw_date(lines[cursor]) is not None:
                break
            cursor += 1
        if cursor + 2 >= len(lines) or lines[cursor] != numbers_label:
            index += 1
            continue
        numbers = re.findall(r"\d{1,2}", lines[cursor + 1])
        special_number = re.fullmatch(r"\d{1,2}", lines[cursor + 2])
        if len(numbers) == 5 and special_number is not None:
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(
                        [
                            *numbers,
                            f"{special_number.group(0)} {special_number_name}",
                        ]
                    ),
                    prizes=(),
                )
            )
        index = cursor + 3
    return tuple(draws)

def _colorado_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A, %m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
