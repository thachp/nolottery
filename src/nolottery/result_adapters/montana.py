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

_MONTANA_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("Mega Ball", {"Mega Ball"}),
    "powerball": ("Powerball", {"PB", "PP"}),
}

def parse_montana_winning_numbers_table(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name, required_headers = _MONTANA_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.winning-numbers-table"):
        headers = {
            header.get_text(" ", strip=True)
            for header in table.select("thead th")
            if header.get_text(" ", strip=True)
        }
        if not required_headers.issubset(headers):
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            draw_date = _montana_draw_date(cells[0].get_text(" ", strip=True))
            primary_numbers = [
                number.strip()
                for number in cells[1].get_text(" ", strip=True).split(",")
                if re.fullmatch(r"\d{1,2}", number.strip())
            ]
            special_number = cells[2].get_text(" ", strip=True)
            if (
                draw_date is None
                or len(primary_numbers) != 5
                or re.fullmatch(r"\d{1,2}", special_number) is None
            ):
                continue
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(
                        [*primary_numbers, f"{special_number} {special_number_name}"]
                    ),
                    prizes=(),
                )
            )
    return tuple(draws)

def _montana_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m.%d.%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
