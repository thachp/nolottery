from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
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

@dataclass(frozen=True)
class _ColoradoGameSpec:
    numbers_label: str
    primary_count: int
    special_number_name: str | None = None


_COLORADO_DRAWING_HISTORY_GAMES = {
    "colorado-cash-5": _ColoradoGameSpec("Cash 5 Numbers", 5),
    "colorado-lotto-plus": _ColoradoGameSpec("Colorado Lotto+ Numbers", 6),
    "colorado-pick-3": _ColoradoGameSpec("Pick 3 Numbers", 3),
    "mega-millions": _ColoradoGameSpec("Mega Millions Numbers", 5, "Mega Ball"),
    "powerball": _ColoradoGameSpec("Powerball Numbers", 5, "Powerball"),
}

def parse_colorado_drawing_history(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    spec = _COLORADO_DRAWING_HISTORY_GAMES[game_slug]
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
        while cursor < len(lines) and lines[cursor] != spec.numbers_label:
            if _colorado_draw_date(lines[cursor]) is not None:
                break
            cursor += 1
        if cursor + 1 >= len(lines) or lines[cursor] != spec.numbers_label:
            index += 1
            continue
        numbers = re.findall(r"\d{1,2}", lines[cursor + 1])
        if len(numbers) != spec.primary_count:
            index += 1
            continue
        if spec.special_number_name is None:
            winning_number = ", ".join(numbers)
            next_index = cursor + 2
        else:
            if cursor + 2 >= len(lines):
                index += 1
                continue
            special_number = re.fullmatch(r"\d{1,2}", lines[cursor + 2])
            if special_number is None:
                index += 1
                continue
            winning_number = ", ".join(
                (
                    *numbers,
                    f"{special_number.group(0)} {spec.special_number_name}",
                )
            )
            next_index = cursor + 3
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
        index = next_index
    return tuple(draws)

def _colorado_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A, %m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        pass
    match = re.fullmatch(
        r"([A-Z][a-z]{2})\. (\d{1,2}), (\d{4}): (Midday|Evening)",
        raw_value,
    )
    if match is None:
        return None
    try:
        parsed = datetime.strptime(
            f"{match.group(1)} {match.group(2)}, {match.group(3)}",
            "%b %d, %Y",
        )
    except ValueError:
        return None
    return f"{parsed.strftime(_DRAW_DATE_FORMAT)} {match.group(4)}"
