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
    "arkansas-cash-3": _ArkansasDidIWinGame(3),
    "arkansas-cash-4": _ArkansasDidIWinGame(4),
    "arkansas-lotto": _ArkansasDidIWinGame(6),
    "arkansas-natural-state-jackpot": _ArkansasDidIWinGame(5),
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
    draws.extend(_parse_arkansas_recent_cards(soup, game_slug, game))
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        draw_date = _arkansas_draw_date(cells[0].get_text(" ", strip=True))
        if draw_date is None:
            continue
        values = _arkansas_row_values(row)
        if len(values) < game.number_count:
            continue
        numbers = tuple(values[: game.number_count])
        special_number = values[game.number_count] if game.special_number_name else None
        if game.special_number_name is not None and special_number is None:
            continue
        winning_parts = [str(number) for number in numbers]
        if special_number is not None and game.special_number_name is not None:
            winning_parts.append(f"{special_number} {game.special_number_name}")
        elif game_slug == "arkansas-lotto" and len(values) > game.number_count:
            winning_parts.append(f"{values[game.number_count]} Bonus Number")
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_parts),
                prizes=(),
            )
        )
    return tuple(draws)


def _parse_arkansas_recent_cards(
    soup: BeautifulSoup,
    game_slug: str,
    game: _ArkansasDidIWinGame,
) -> list[ParsedDraw]:
    if game_slug not in {"arkansas-cash-3", "arkansas-cash-4"}:
        return []
    draws: list[ParsedDraw] = []
    for card in soup.select(".draw-game__numbers-container"):
        label = card.find("strong")
        if label is None:
            continue
        draw_date = _arkansas_draw_date(label.get_text(" ", strip=True))
        if draw_date is None:
            continue
        numbers = [
            number.get_text(" ", strip=True)
            for number in card.select(".draw-game__number")
        ]
        if len(numbers) != game.number_count:
            continue
        if not all(re.fullmatch(r"\d", number) for number in numbers):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return draws


def _arkansas_row_values(row: Tag) -> tuple[int, ...]:
    value_cells = row.find_all("td")[1:]
    list_items = [
        item.get_text(" ", strip=True)
        for cell in value_cells
        for item in cell.find_all("li")
    ]
    if list_items:
        return tuple(_int_from_text(item) for item in list_items)
    values = [cell.get_text(" ", strip=True) for cell in value_cells]
    if not all(re.fullmatch(r"\d{1,2}", value) for value in values):
        return ()
    return tuple(int(value) for value in values)


def _arkansas_draw_date(raw_value: str) -> str | None:
    cleaned = raw_value.strip()
    session = ""
    if cleaned.endswith(" Drawing"):
        cleaned = cleaned[: -len(" Drawing")]
    for suffix in (" Evening", " Midday"):
        if cleaned.endswith(suffix):
            session = suffix
            cleaned = cleaned[: -len(suffix)]
            break
    try:
        return datetime.strptime(cleaned, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT) + session
    except ValueError:
        pass
    try:
        return datetime.strptime(cleaned, "%B %d, %Y").strftime(_DRAW_DATE_FORMAT) + session
    except ValueError:
        return None
