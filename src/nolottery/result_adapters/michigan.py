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

_MICHIGAN_DRAW_HISTORY_GAMES = {
    "mega-millions": ("B", "megaball", "Mega Ball"),
    "powerball": ("P", "powerball", "Powerball"),
}

_MICHIGAN_DRAW_HISTORY_QUERY = """
query Game($gameCode: String!, $startDateString: String!, $endDateString: String!) {
  gameByCode(code: $gameCode) {
    logicalGameIdentifier
    drawResultsBetweenDates(
      startDateString: $startDateString,
      endDateString: $endDateString
    ) {
      drawDate
      drawSequence
      hasPayoutData
      isBonusDraw
      winningNumbers {
        drawNumbers
        powerball
        powerplay
        megaball
        megaplier
      }
    }
  }
}
"""

def parse_michigan_draw_history_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, special_key, special_number_name = _MICHIGAN_DRAW_HISTORY_GAMES[game_slug]
    payload = json.loads(raw_json)
    game_data = payload.get("data", {}).get("gameByCode") if isinstance(payload, dict) else None
    if not isinstance(game_data, dict):
        return ()
    raw_draws = game_data.get("drawResultsBetweenDates")
    if not isinstance(raw_draws, list):
        return ()

    draws: list[ParsedDraw] = []
    for item in raw_draws:
        if not isinstance(item, dict):
            continue
        if _int_value(item.get("drawSequence")) != 1:
            continue

        winning_numbers = item.get("winningNumbers")
        if not isinstance(winning_numbers, dict):
            continue
        raw_numbers = winning_numbers.get("drawNumbers")
        if not isinstance(raw_numbers, list):
            continue
        primary_numbers = [
            str(number)
            for raw_number in raw_numbers[:5]
            if (number := _int_value(raw_number)) is not None
        ]
        special_number = _int_value(winning_numbers.get(special_key))
        draw_date = _michigan_draw_date(item.get("drawDate"))
        if draw_date is None or len(primary_numbers) != 5 or special_number is None:
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

def _michigan_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None

def _michigan_draw_history_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-mi-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_code, _, _ = _MICHIGAN_DRAW_HISTORY_GAMES[game.slug]
    end_date = datetime.now(tz=UTC)
    start_date = datetime.fromordinal(end_date.date().toordinal() - 180).replace(
        tzinfo=UTC
    )
    source_url = "https://www.michiganlottery.com/api"
    payload = json.dumps(
        {
            "query": _MICHIGAN_DRAW_HISTORY_QUERY,
            "variables": {
                "gameCode": game_code,
                "startDateString": start_date.isoformat().replace("+00:00", "Z"),
                "endDateString": end_date.isoformat().replace("+00:00", "Z"),
            },
        }
    )
    response = httpx.post(
        source_url,
        content=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)
