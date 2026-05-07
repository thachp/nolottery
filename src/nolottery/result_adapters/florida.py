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

_FLORIDA_PICK_GAMES = {
    "florida-pick-2": ("https://files.floridalottery.com/exptkt/p2.pdf", 2),
    "florida-pick-3": ("https://files.floridalottery.com/exptkt/p3.pdf", 3),
    "florida-pick-4": ("https://files.floridalottery.com/exptkt/p4.pdf", 4),
    "florida-pick-5": ("https://files.floridalottery.com/exptkt/p5.pdf", 5),
}

def _florida_pick_history_draws(
    game_slug: str,
    *,
    source_dir: Path | None,
) -> tuple[str, str, tuple[ParsedDraw, ...]]:
    raw_text, source_url = _read_florida_pick_history_source(game_slug, source_dir)
    return raw_text, source_url, parse_florida_pick_history_text(raw_text, game_slug)

def parse_florida_pick_history_text(
    raw_text: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, digit_count = _FLORIDA_PICK_GAMES[game_slug]
    number_pattern = r"\d" + (r"\s*-\s*\d" * (digit_count - 1))
    entry_re = re.compile(
        rf"(?P<date>\d{{2}}/\d{{2}}/\d{{2}})\s+"
        rf"(?P<session>[EM])\s+"
        rf"(?P<numbers>{number_pattern})\s+FB\s+\d"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        parsed_date = datetime.strptime(match.group("date"), "%m/%d/%y")
        session = "Evening" if match.group("session") == "E" else "Midday"
        numbers = re.findall(r"\d", match.group("numbers"))
        draws.append(
            ParsedDraw(
                draw_date=f"{parsed_date.strftime(_DRAW_DATE_FORMAT)} {session}",
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)

def _read_florida_pick_history_source(
    game_slug: str,
    source_dir: Path | None,
) -> tuple[str, str]:
    history_url, _ = _FLORIDA_PICK_GAMES[game_slug]
    source_name = f"{game_slug}-fl-backfill"
    if source_dir is not None:
        text_file = source_dir / f"{source_name}.txt"
        if text_file.exists():
            return text_file.read_text(encoding="utf-8"), text_file.as_uri()
        pdf_file = source_dir / f"{source_name}.pdf"
        return _extract_pdf_text(pdf_file.read_bytes()), pdf_file.as_uri()

    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")
    with httpx.Client(
        follow_redirects=True,
        timeout=30,
        verify=ssl_context,
    ) as client:
        response = client.get(history_url)
    response.raise_for_status()
    return _extract_pdf_text(response.content), str(response.url)
