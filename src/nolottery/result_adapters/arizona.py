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

_ARIZONA_PAST_180_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}

def _arizona_past_180_draws(
    game: GameMetadata,
    *,
    source_dir: Path | None,
) -> tuple[str, str, tuple[ParsedDraw, ...]]:
    raw_text, source_url = _read_arizona_past_180_source(game, source_dir)
    return raw_text, source_url, parse_arizona_past_180_text(raw_text, game.slug)

def parse_arizona_past_180_text(
    raw_text: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ARIZONA_PAST_180_GAMES[game_slug]
    special_label = "MEGA BALL" if game_slug == "mega-millions" else "POWER BALL"
    entry_re = re.compile(
        rf"DRAW DATE\s+(?P<date>\d{{4}}-\d{{2}}-\d{{2}}).*?"
        rf"WINNING NUMBERS\s+(?P<numbers>\d{{1,2}}\s*-\s*\d{{1,2}}\s*-\s*"
        rf"\d{{1,2}}\s*-\s*\d{{1,2}}\s*-\s*\d{{1,2}}).*?"
        rf"{special_label}\s+(?P<special>\d{{1,2}})",
        re.DOTALL,
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        draw_date = _arizona_draw_date(match.group("date"))
        if draw_date is None:
            continue
        numbers = re.findall(r"\d{1,2}", match.group("numbers"))
        special_number = match.group("special")
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _arizona_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _read_arizona_past_180_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-az-backfill"
    if source_dir is not None:
        text_file = source_dir / f"{source_name}.txt"
        if text_file.exists():
            return text_file.read_text(encoding="utf-8"), text_file.as_uri()
        pdf_file = source_dir / f"{source_name}.pdf"
        return _extract_pdf_text(pdf_file.read_bytes()), pdf_file.as_uri()

    response = httpx.get(game.source_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return _extract_pdf_text(response.content), str(response.url)
