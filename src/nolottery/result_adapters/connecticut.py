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

_CONNECTICUT_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("11", "MegaMillions", "Mega Ball"),
    "powerball": ("5", "Powerball", "Powerball"),
}

def parse_connecticut_winning_numbers(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, _, special_number_name = _CONNECTICUT_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("#gvWinningNumbers tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if not cells:
            continue
        if game_slug == "powerball":
            if len(cells) < 4 or cells[0] != "Powerball":
                continue
            raw_date, raw_numbers, raw_special = cells[1], cells[2], cells[3]
        else:
            if len(cells) < 3:
                continue
            raw_date, raw_numbers, raw_special = cells[0], cells[1], cells[2]
        draw_date = _connecticut_draw_date(raw_date)
        numbers = re.findall(r"\d{1,2}", raw_numbers)
        special_number = re.search(r"\d{1,2}", raw_special)
        if draw_date is None or len(numbers) != 5 or special_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number.group(0)} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _connecticut_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _connecticut_winning_numbers_draws_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    game_id, page_name, _ = _CONNECTICUT_WINNING_NUMBERS_GAMES[game.slug]
    source_name = f"{game.slug}-ct-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.html"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    end_date = date.today()
    start_date = date.fromordinal(end_date.toordinal() - 180)
    query = urlencode(
        {
            "g": game_id,
            "s": start_date.strftime("%m/%d/%Y"),
            "e": end_date.strftime("%m/%d/%Y"),
        }
    )
    source_url = f"https://www.ctlottery.org/ajax/getWinningNumbers?{query}"
    headers = {
        "Referer": f"https://www.ctlottery.org/WinningNumbers/{page_name}",
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }
    response = httpx.get(
        source_url,
        headers=headers,
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)
