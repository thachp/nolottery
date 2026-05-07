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

_MISSOURI_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("num_yellow", "Mega Ball"),
    "powerball": ("num_red", "Powerball"),
}

def parse_missouri_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_class, special_number_name = _MISSOURI_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("table.table_game tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        draw_date = _missouri_draw_date(cells[0].get_text(" ", strip=True))
        number_nodes = cells[1].select(".num_small")
        if len(number_nodes) < 6:
            continue
        special_node = number_nodes[5]
        if special_class not in special_node.get("class", ()):
            continue
        numbers = [
            item.get_text(" ", strip=True)
            for item in number_nodes[:6]
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        if draw_date is None or len(numbers) != 6:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers[:5], f"{numbers[5]} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _missouri_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
