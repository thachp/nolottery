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

_MISSISSIPPI_DAILY_GAMES = {
    "mississippi-cash-3": ("cash-3", 3),
    "mississippi-cash-4": ("cash-4", 4),
}
_MISSISSIPPI_HOME_PAGE_ALL_GAMES = {
    **_MISSISSIPPI_HOME_PAGE_GAMES,
    **_MISSISSIPPI_DAILY_GAMES,
}

def parse_mississippi_home_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if game_slug in _MISSISSIPPI_DAILY_GAMES:
        return _parse_mississippi_daily_game(raw_html, game_slug)

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

def _parse_mississippi_daily_game(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_path, digit_count = _MISSISSIPPI_DAILY_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    game_link = soup.select_one(f'a[href*="/games/{game_path}/"]')
    if game_link is None:
        return ()
    game_container = game_link.find_parent(
        class_=lambda value: value and "drawgamewrap" in value.split()
    )
    if not isinstance(game_container, Tag):
        return ()

    draws: list[ParsedDraw] = []
    for session_node in game_container.select(".drawn-numbers"):
        draw_date_node = session_node.select_one(".latestdraw")
        number_container = session_node.select_one(".results-wrap")
        if draw_date_node is None or number_container is None:
            continue
        draw_date = _mississippi_daily_draw_date(
            draw_date_node.get_text(" ", strip=True)
        )
        numbers = [
            item.get_text(" ", strip=True)
            for item in number_container.select("i:not(.fireball)")
            if re.fullmatch(r"\d", item.get_text(" ", strip=True))
        ][:digit_count]
        if draw_date is None or len(numbers) != digit_count:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)

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

def _mississippi_daily_draw_date(raw_value: str) -> str | None:
    match = re.search(r"\b(\d{2}/\d{2})\s+(MIDDAY|EVE)\b", raw_value)
    if match is None:
        return None
    session = "Midday" if match.group(2) == "MIDDAY" else "Evening"
    draw_date = _mississippi_draw_date(match.group(1))
    if draw_date is None:
        return None
    return f"{draw_date} {session}"
