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

_MINNESOTA_WINNING_NUMBERS_GAMES = {
    "lotto-america": ("Lotto America", 5, "Star Ball"),
    "mega-millions": ("Mega Millions", 5, "Mega Ball"),
    "minnesota-pick-3": ("Pick 3", 3, None),
    "powerball": ("Powerball", 5, "Powerball"),
}

def parse_minnesota_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_label, primary_count, special_number_name = _MINNESOTA_WINNING_NUMBERS_GAMES[
        game_slug
    ]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for card in soup.select("figure.card--winning-numbers"):
        heading = card.select_one("h4")
        if heading is None:
            continue
        if heading.get_text(" ", strip=True) != game_label:
            continue

        draw_date_node = card.select_one(".lottery-drawing span")
        draw_date = (
            _minnesota_draw_date(draw_date_node.get_text(" ", strip=True))
            if draw_date_node is not None
            else None
        )
        numbers = [
            item.get_text(" ", strip=True)
            for item in card.select(".lottery-number-list-item")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        expected_count = primary_count + (1 if special_number_name is not None else 0)
        if draw_date is None or len(numbers) != expected_count:
            continue
        winning_numbers = numbers
        if special_number_name is not None:
            winning_numbers = [
                *numbers[:primary_count],
                f"{numbers[-1]} {special_number_name}",
            ]

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_numbers),
                prizes=(),
            )
        )
    return tuple(draws)

def _minnesota_draw_date(raw_value: str) -> str | None:
    normalized = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw_value)
    try:
        return datetime.strptime(normalized, "%B %d, %Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
