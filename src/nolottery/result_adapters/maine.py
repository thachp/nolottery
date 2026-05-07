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

_MAINE_HOME_PAGE_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}

def parse_maine_home_page(raw_html: str, game_slug: str) -> tuple[ParsedDraw, ...]:
    game_label, special_number_name = _MAINE_HOME_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    image = soup.find("img", alt=re.compile(rf"^{re.escape(game_label)}$", re.I))
    if not isinstance(image, Tag):
        return ()
    block = _maine_game_block_text(image)
    date_match = re.search(r"\b[A-Z][a-z]+ \d{2}/\d{2}/\d{4}\b", block)
    if date_match is None:
        return ()
    numbers = [
        number
        for number in re.findall(r"\b\d{1,2}\b", block[date_match.end() :])
    ][:6]
    if len(numbers) != 6:
        return ()
    draw_date = _maine_draw_date(date_match.group(0))
    if draw_date is None:
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

def _maine_game_block_text(image: Tag) -> str:
    parts: list[str] = []
    for node in image.next_elements:
        if isinstance(node, Tag) and node.name == "img":
            break
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parts.append(text)
    return " ".join(parts)

def _maine_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A %m/%d/%Y").strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None
