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

_MASSACHUSETTS_DRAW_RESULTS_GAMES = {
    "mega-millions": ("mega_millions", "megaball", "Mega Ball"),
    "powerball": ("powerball", "powerball", "Powerball"),
}

def parse_massachusetts_draw_results_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_identifier, special_key, special_number_name = (
        _MASSACHUSETTS_DRAW_RESULTS_GAMES[game_slug]
    )
    payload = json.loads(raw_json)
    raw_draws = payload.get("winningNumbers") if isinstance(payload, dict) else None
    if not isinstance(raw_draws, list):
        return ()

    draws: list[ParsedDraw] = []
    for item in raw_draws:
        if not isinstance(item, dict):
            continue
        if item.get("gameIdentifier") != game_identifier:
            continue
        if item.get("status") != "COMPLETE":
            continue

        draw_date = _massachusetts_draw_date(item.get("drawDate"))
        raw_numbers = item.get("winningNumbers")
        extras = item.get("extras")
        if not isinstance(raw_numbers, list) or not isinstance(extras, dict):
            continue

        primary_numbers = [
            str(number)
            for raw_number in raw_numbers[:5]
            if (number := _int_value(raw_number)) is not None
        ]
        special_number = _int_value(extras.get(special_key))
        if draw_date is None or len(primary_numbers) != 5 or special_number is None:
            continue

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [
                        *primary_numbers,
                        f"{special_number} {special_number_name}",
                    ]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _massachusetts_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _massachusetts_draw_results_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ma-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    source_url = "https://www.masslottery.com/api/v1/draw-results"
    response = httpx.get(source_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return response.text, str(response.url)
