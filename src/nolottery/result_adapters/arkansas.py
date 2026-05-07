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

_ARKANSAS_DID_I_WIN_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

def parse_arkansas_did_i_win(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ARKANSAS_DID_I_WIN_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) < 7:
            continue
        draw_date = _arkansas_draw_date(cells[0])
        if draw_date is None:
            continue
        numbers = tuple(cells[1:6])
        special_number = cells[6]
        if not all(re.fullmatch(r"\d{1,2}", value) for value in (*numbers, special_number)):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _arkansas_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
