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

_NEW_YORK_DAILY_NUMBERS_URL = (
    "https://data.ny.gov/resource/hsys-3def.json?"
    "$limit=50000&$order=draw_date%20DESC"
)

_NEW_YORK_DAILY_GAMES = {"numbers", "win-4"}

def parse_new_york_daily_numbers_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    payload = json.loads(raw_json)
    field_names = (
        ("midday_daily", "evening_daily")
        if game_slug == "numbers"
        else ("midday_win_4", "evening_win_4")
    )
    draws: list[ParsedDraw] = []
    for item in payload:
        draw_date = _new_york_draw_date(item.get("draw_date"))
        if draw_date is None:
            continue
        for field_name, session in zip(field_names, ("Midday", "Evening"), strict=True):
            number = item.get(field_name)
            if isinstance(number, str) and number.strip():
                draws.append(
                    ParsedDraw(
                        draw_date=f"{draw_date} {session}",
                        winning_number=number.strip(),
                        prizes=(),
                    )
                )
    return tuple(draws)

def _new_york_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    return datetime.fromisoformat(raw_value).strftime(_DRAW_DATE_FORMAT)
