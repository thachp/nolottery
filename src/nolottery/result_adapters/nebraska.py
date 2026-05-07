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

_NEBRASKA_DRAW_RESULTS_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}

def parse_nebraska_draw_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_name, special_number_name = _NEBRASKA_DRAW_RESULTS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    heading = next(
        (
            heading
            for heading in soup.select("h3")
            if heading.get_text(" ", strip=True) == f"{game_name} Numbers"
        ),
        None,
    )
    if heading is None:
        return ()
    table = heading.find_next("table", class_="numbertable")
    if table is None:
        return ()

    draws: list[ParsedDraw] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        draw_date = _nebraska_draw_date(cells[0].get_text(" ", strip=True))
        primary_numbers = [
            number
            for raw_number in cells[1].get_text(" ", strip=True).split(",")
            if (number := _nebraska_number(raw_number)) is not None
        ]
        special_number = _nebraska_number(cells[2].get_text(" ", strip=True))
        if (
            draw_date is None
            or len(primary_numbers) != 5
            or special_number is None
        ):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [
                        *primary_numbers,
                        f"{special_number} {special_number_name}",
                    ]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _nebraska_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _nebraska_number(raw_value: str) -> str | None:
    value = raw_value.strip()
    if re.fullmatch(r"\d{1,2}", value) is None:
        return None
    return str(int(value))
