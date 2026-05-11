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
class _ArkansasDidIWinGame:
    number_count: int
    special_number_name: str | None = None


_ARKANSAS_DID_I_WIN_GAMES = {
    "arkansas-lotto": _ArkansasDidIWinGame(6),
    "lucky-for-life": _ArkansasDidIWinGame(5, "Lucky Ball"),
    "millionaire-for-life": _ArkansasDidIWinGame(5, "Millionaire Ball"),
    "mega-millions": _ArkansasDidIWinGame(5, "Mega Ball"),
    "powerball": _ArkansasDidIWinGame(5, "Powerball"),
}


def parse_arkansas_did_i_win(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game = _ARKANSAS_DID_I_WIN_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        expected_cell_count = game.number_count + 1
        if game.special_number_name is not None:
            expected_cell_count += 1
        if len(cells) < expected_cell_count:
            continue
        draw_date = _arkansas_draw_date(cells[0])
        if draw_date is None:
            continue
        numbers = tuple(cells[1 : 1 + game.number_count])
        special_number = cells[1 + game.number_count] if game.special_number_name else None
        values = (*numbers, special_number) if special_number is not None else numbers
        if not all(re.fullmatch(r"\d{1,2}", value) for value in values):
            continue
        winning_parts = list(numbers)
        if special_number is not None:
            winning_parts.append(f"{special_number} {game.special_number_name}")
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_parts),
                prizes=(),
            )
        )
    return tuple(draws)


def _arkansas_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
