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

_MISSISSIPPI_HOME_PAGE_GAMES = {
    "mega-millions": ("mega-millions", "Mega Ball"),
    "powerball": ("powerball", "Powerball"),
}

def parse_mississippi_home_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_path, special_number_name = _MISSISSIPPI_HOME_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    game_link = soup.select_one(f'a[href*="/games/{game_path}/"]')
    if game_link is None:
        return ()
    game_container = game_link.find_parent(
        class_=lambda value: value and "drawgamewrap" in value.split()
    )
    if not isinstance(game_container, Tag):
        return ()

    draw_date_node = game_container.select_one(".latestdraw")
    number_container = game_container.select_one(".lotto-numbers")
    if draw_date_node is None or number_container is None:
        return ()
    draw_date = _mississippi_draw_date(draw_date_node.get_text(" ", strip=True))
    numbers = [
        item.get_text(" ", strip=True)
        for item in number_container.select("i")
        if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
    ][:6]
    if draw_date is None or len(numbers) != 6:
        return ()

    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*numbers[:5], f"{numbers[5]} {special_number_name}"]
            ),
            prizes=(),
        ),
    )

def _mississippi_draw_date(raw_value: str) -> str | None:
    match = re.search(r"\b(\d{2}/\d{2})\b", raw_value)
    if match is None:
        return None
    try:
        return datetime.strptime(
            f"{match.group(1)}/{date.today().year}",
            "%m/%d/%Y",
        ).strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
