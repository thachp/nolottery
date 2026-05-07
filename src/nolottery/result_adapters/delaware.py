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

_DELAWARE_SEARCH_WINNERS_GAMES = {
    "mega-millions": ("MEGA-MILLIONS", "Mega Millions", "Mega Ball"),
    "powerball": ("POWERBALL", "Powerball", "Powerball"),
}

def parse_delaware_search_winners(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, game_name, special_number_name = _DELAWARE_SEARCH_WINNERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("table.table-winning-numbers-search-results tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        row_game = _delaware_row_game(cells[0])
        if row_game != game_name:
            continue
        draw_date = _delaware_draw_date(cells[1].get_text(" ", strip=True))
        numbers = [item.get_text(" ", strip=True) for item in cells[2].select("li")]
        if draw_date is None or len(numbers) != 6:
            continue
        primary_numbers = [number for number in numbers[:5] if re.fullmatch(r"\d{1,2}", number)]
        special_number = numbers[5]
        if len(primary_numbers) != 5 or not re.fullmatch(r"\d{1,2}", special_number):
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

def _delaware_row_game(cell: Tag) -> str:
    for text in cell.stripped_strings:
        return text
    return ""

def _delaware_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _delaware_search_winners_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-de-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.html"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_path, _, _ = _DELAWARE_SEARCH_WINNERS_GAMES[game.slug]
    today = date.today()
    source_url = (
        "https://www.delottery.com/Winning-Numbers/Search-Winners/"
        f"{today.year}/{today.month}/{game_path}"
    )
    response = httpx.get(source_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text, str(response.url)
