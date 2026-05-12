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
    "michigan-fantasy-5": ((("5", None),), 5, None, None),
    "michigan-keno": ((("K", None),), 22, None, None),
    "michigan-lotto-47": ((("6", None),), 6, None, None),
    "michigan-poker-lotto": ((("C", None),), 5, None, None),
    "mega-millions": ((("B", None),), 5, "megaball", "Mega Ball"),
    "michigan-daily-3": ((("T", "Midday"), ("3", "Evening")), 3, None, None),
    "michigan-daily-4": ((("F", "Midday"), ("4", "Evening")), 4, None, None),
    "millionaire-for-life": ((("U", None),), 5, "millionaireball", "Millionaire Ball"),
    "powerball": ((("P", None),), 5, "powerball", "Powerball"),
}

_MICHIGAN_DRAW_RANGE_GAMES = {
    "michigan-cash-pop": ("H", "CASH_POP", 1, None),
    "michigan-club-keno": ("Q", "CLUB_KENO", 20, "Kicker"),
}

_MICHIGAN_GRAPHQL_GAMES = {
    **_MICHIGAN_DRAW_HISTORY_GAMES,
    **_MICHIGAN_DRAW_RANGE_GAMES,
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
        luckyball
        millionaireball
        kicker
      }
    }
  }
}
"""

_MICHIGAN_DRAW_RANGE_QUERY = """
query Game($gameCode: String!, $startDrawNumber: Int!, $endDrawNumber: Int!) {
  gameByCode(code: $gameCode) {
    drawResultsForDrawNumberRange(
      startDrawNumber: $startDrawNumber,
      endDrawNumber: $endDrawNumber
    ) {
      drawNumber
      winningNumbers {
        drawNumbers
        kicker
        clubKenoExtraNumbers
        clubKenoPlus3Numbers
      }
    }
  }
}
"""

_MICHIGAN_CURRENT_DRAW_QUERY = """
query gameCardData($logicalGameIdentifier: String) {
  drawGame(logicalGameIdentifier: $logicalGameIdentifier) {
    lastReceivedDrawResult {
      drawNumber
    }
  }
}
"""

def parse_michigan_graphql_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if game_slug in _MICHIGAN_DRAW_RANGE_GAMES:
        return parse_michigan_draw_range_json(raw_json, game_slug)
    return parse_michigan_draw_history_json(raw_json, game_slug)

def parse_michigan_draw_history_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, primary_count, special_key, special_number_name = _MICHIGAN_DRAW_HISTORY_GAMES[
        game_slug
    ]
    payload = json.loads(raw_json)
    if isinstance(payload, dict) and isinstance(payload.get("responses"), list):
        return tuple(
            draw
            for response in payload["responses"]
            if isinstance(response, dict)
            for draw in _parse_michigan_draw_history_payload(
                response.get("payload"),
                primary_count=primary_count,
                special_key=special_key,
                special_number_name=special_number_name,
                session=response.get("session") if isinstance(response.get("session"), str) else None,
            )
        )
    return _parse_michigan_draw_history_payload(
        payload,
        primary_count=primary_count,
        special_key=special_key,
        special_number_name=special_number_name,
    )

def parse_michigan_draw_range_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, _, primary_count, special_number_name = _MICHIGAN_DRAW_RANGE_GAMES[game_slug]
    payload = json.loads(raw_json)
    game_data = (
        payload.get("data", {}).get("gameByCode") if isinstance(payload, dict) else None
    )
    if not isinstance(game_data, dict):
        return ()
    raw_draws = game_data.get("drawResultsForDrawNumberRange")
    if not isinstance(raw_draws, list):
        return ()

    draws: list[ParsedDraw] = []
    for item in raw_draws:
        if not isinstance(item, dict):
            continue
        draw_number = _int_value(item.get("drawNumber"))
        winning_numbers = item.get("winningNumbers")
        if draw_number is None or not isinstance(winning_numbers, dict):
            continue
        raw_numbers = winning_numbers.get("drawNumbers")
        if not isinstance(raw_numbers, list):
            continue
        primary_numbers = [
            str(number)
            for raw_number in raw_numbers[:primary_count]
            if (number := _int_value(raw_number)) is not None
        ]
        if len(primary_numbers) != primary_count:
            continue
        winning_number_parts = primary_numbers
        if special_number_name is not None:
            special_number = _int_value(winning_numbers.get("kicker"))
            if special_number is not None:
                winning_number_parts = [
                    *primary_numbers,
                    f"{special_number} {special_number_name}",
                ]
        draws.append(
            ParsedDraw(
                draw_date=f"Draw {draw_number}",
                winning_number=", ".join(winning_number_parts),
                prizes=(),
            )
        )
    return tuple(draws)

def _parse_michigan_draw_history_payload(
    payload: object,
    *,
    primary_count: int,
    special_key: str | None,
    special_number_name: str | None,
    session: str | None = None,
) -> tuple[ParsedDraw, ...]:
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
            for raw_number in raw_numbers[:primary_count]
            if (number := _int_value(raw_number)) is not None
        ]
        special_number = (
            _int_value(winning_numbers.get(special_key))
            if special_key is not None
            else None
        )
        draw_date = _michigan_draw_date(item.get("drawDate"))
        if draw_date is None or len(primary_numbers) != primary_count:
            continue
        if session is not None:
            draw_date = f"{draw_date} {session}"
        if special_key is not None and special_number is None:
            continue
        winning_number_parts = primary_numbers
        if special_number_name is not None:
            winning_number_parts = [
                *primary_numbers,
                f"{special_number} {special_number_name}",
            ]

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(winning_number_parts),
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

    game_codes, _, _, _ = _MICHIGAN_DRAW_HISTORY_GAMES[game.slug]
    end_date = datetime.now(tz=UTC)
    start_date = datetime.fromordinal(end_date.date().toordinal() - 180).replace(
        tzinfo=UTC
    )
    source_url = "https://www.michiganlottery.com/api"
    responses: list[dict[str, object]] = []
    for game_code, session in game_codes:
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
        responses.append(
            {
                "game_code": game_code,
                "session": session,
                "payload": response.json(),
            }
        )
    if len(responses) == 1:
        return json.dumps(responses[0]["payload"]), source_url
    return json.dumps({"responses": responses}), source_url

def _michigan_draw_range_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-mi-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_code, logical_game_identifier, _, _ = _MICHIGAN_DRAW_RANGE_GAMES[game.slug]
    source_url = "https://www.michiganlottery.com/api"
    current_response = httpx.post(
        source_url,
        content=json.dumps(
            {
                "query": _MICHIGAN_CURRENT_DRAW_QUERY,
                "variables": {"logicalGameIdentifier": logical_game_identifier},
            }
        ),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    current_response.raise_for_status()
    current_draw = _michigan_current_draw_number(current_response.json())
    if current_draw is None:
        return json.dumps({}), source_url

    start_draw = max(1, current_draw - 179)
    range_response = httpx.post(
        source_url,
        content=json.dumps(
            {
                "query": _MICHIGAN_DRAW_RANGE_QUERY,
                "variables": {
                    "gameCode": game_code,
                    "startDrawNumber": start_draw,
                    "endDrawNumber": current_draw,
                },
            }
        ),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    range_response.raise_for_status()
    return range_response.text, source_url

def _michigan_current_draw_number(payload: object) -> int | None:
    draw_result = (
        payload.get("data", {})
        .get("drawGame", {})
        .get("lastReceivedDrawResult")
        if isinstance(payload, dict)
        else None
    )
    if not isinstance(draw_result, dict):
        return None
    return _int_value(draw_result.get("drawNumber"))
