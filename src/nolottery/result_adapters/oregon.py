from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode, urljoin

import httpx

from nolottery.fetch_models import ParsedDraw
from nolottery.metadata import GameMetadata
from nolottery.result_adapters.common import (
    AdapterFetch,
    SourceReader,
    SourceSnapshot,
    _DRAW_DATE_FORMAT,
)

_OREGON_DRAW_GAME_SELECTORS = {
    "oregon-megabucks": "mb",
    "oregon-cash-pop": "cp",
    "oregon-pick-4": "p4",
    "oregon-win-for-life": "wf",
}
_OREGON_KENO_GAMES = {"oregon-keno"}
_OREGON_API_GAMES = frozenset((*_OREGON_DRAW_GAME_SELECTORS, *_OREGON_KENO_GAMES))
_OREGON_BACKFILL_DAYS = 365


@dataclass(frozen=True)
class _OregonApiConfig:
    api_url: str
    api_key: str


def fetch_oregon_result(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    discovery_html, discovery_url = read_source(
        game.source_url,
        source_dir,
        f"{game.slug}-or-discovery",
    )
    config = _parse_oregon_api_config(discovery_html)
    today = datetime.now(tz=UTC).date()
    if game.slug in _OREGON_KENO_GAMES:
        start_date = today
    else:
        start_date = today - timedelta(days=_OREGON_BACKFILL_DAYS)
    api_url = _oregon_api_url(game.slug, config.api_url, start_date, today)
    if source_dir is None:
        raw_json, source_url = _read_oregon_api(api_url, config.api_key)
    else:
        raw_json, source_url = read_source(
            api_url,
            source_dir,
            f"{game.slug}-or-backfill",
            suffix=".json",
        )

    draws = parse_oregon_api_results_json(raw_json, game.slug)
    return AdapterFetch(
        source_url=discovery_url,
        draws=draws,
        snapshots=(SourceSnapshot(source_url, raw_json, draws),),
        page_count=1,
    )


def parse_oregon_api_results_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if game_slug == "oregon-keno":
        return parse_oregon_keno_json(raw_json)
    return parse_oregon_draw_results_json(raw_json, game_slug)


def parse_oregon_draw_results_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    draws: list[ParsedDraw] = []
    for record in _records(raw_json):
        numbers = _winning_numbers(record)
        if game_slug == "oregon-megabucks":
            winning_numbers = tuple(number for number in numbers[:6] if number > 0)
            if len(winning_numbers) != 6:
                continue
            draw_date = _draw_date(record, keep_time=False)
        elif game_slug == "oregon-cash-pop":
            winning_numbers = tuple(number for number in numbers[:1] if number > 0)
            if len(winning_numbers) != 1:
                continue
            draw_date = _draw_date(record, keep_time=True)
        elif game_slug == "oregon-pick-4":
            winning_numbers = numbers[:4]
            if len(winning_numbers) != 4:
                continue
            draw_date = _draw_date(record, keep_time=True)
        elif game_slug == "oregon-win-for-life":
            winning_numbers = tuple(number for number in numbers[:4] if number > 0)
            if len(winning_numbers) != 4:
                continue
            draw_date = _draw_date(record, keep_time=False)
        else:
            continue
        if draw_date is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    _format_number(number) for number in winning_numbers
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def parse_oregon_keno_json(raw_json: str) -> tuple[ParsedDraw, ...]:
    draws: list[ParsedDraw] = []
    for record in _records(raw_json):
        numbers = _winning_numbers(record)
        if len(numbers) != 20:
            continue
        bulls_eye = _int_value(
            record.get("BullsEye")
            or record.get("BullsEyeNumber")
            or record.get("Bulls-eye")
        )
        if bulls_eye is None:
            continue
        draw_date = _draw_date(record, keep_time=True)
        if draw_date is None:
            continue
        winning_numbers = ", ".join(_format_number(number) for number in numbers)
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=f"{winning_numbers}, {_format_number(bulls_eye)} Bulls-eye",
                prizes=(),
            )
        )
    return tuple(draws)


def _parse_oregon_api_config(raw_html: str) -> _OregonApiConfig:
    olapi_match = re.search(r"var\s+olapi\s*=\s*(\{.*?\});", raw_html, re.DOTALL)
    if olapi_match is not None:
        payload = json.loads(olapi_match.group(1))
        api_url = str(payload.get("url") or "")
        api_key = str(payload.get("apikey") or "")
        if api_url and api_key:
            return _OregonApiConfig(api_url=api_url, api_key=api_key)

    api_key_match = re.search(r'"apikey"\s*:\s*"([^"]+)"', raw_html)
    api_url_match = re.search(r"https://api2\.oregonlottery\.org", raw_html)
    if api_url_match is None or api_key_match is None:
        raise ValueError("could not find Oregon Lottery API configuration")
    return _OregonApiConfig(
        api_url=api_url_match.group(0),
        api_key=api_key_match.group(1),
    )


def _oregon_api_url(
    game_slug: str,
    api_base_url: str,
    start_date: date,
    end_date: date,
) -> str:
    query = {
        "startingDate": _api_date(start_date),
        "endingDate": _api_date(end_date),
    }
    if game_slug == "oregon-keno":
        query["pageSize"] = "400"
        return urljoin(api_base_url, f"/keno/ByDrawDate?{urlencode(query)}")

    query["gameSelector"] = _OREGON_DRAW_GAME_SELECTORS[game_slug]
    query["pageSize"] = "1000"
    query["includeOpen"] = "False"
    return urljoin(api_base_url, f"/drawresults/ByDrawDate?{urlencode(query)}")


def _read_oregon_api(api_url: str, api_key: str) -> tuple[str, str]:
    response = httpx.get(
        api_url,
        headers={"Ocp-Apim-Subscription-Key": api_key},
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)


def _api_date(value: date) -> str:
    return f"{value.month}-{value.day}-{value.year}"


def _records(raw_json: str) -> tuple[dict[str, object], ...]:
    payload = json.loads(raw_json)
    if isinstance(payload, list):
        return tuple(record for record in payload if isinstance(record, dict))
    if isinstance(payload, dict):
        for key in ("DrawResults", "Results", "data", "items"):
            records = payload.get(key)
            if isinstance(records, list):
                return tuple(record for record in records if isinstance(record, dict))
    return ()


def _winning_numbers(record: dict[str, object]) -> tuple[int, ...]:
    raw_numbers = record.get("WinningNumbers") or record.get("winningNumbers")
    if not isinstance(raw_numbers, list):
        return ()
    return tuple(
        number
        for raw_number in raw_numbers
        if (number := _int_value(raw_number)) is not None
    )


def _draw_date(record: dict[str, object], *, keep_time: bool) -> str | None:
    raw_candidates = [
        record.get("DrawDateTime"),
        record.get("drawDateTime"),
        record.get("RoundedDrawDateTime"),
        record.get("roundedDrawDateTime"),
        record.get("DrawDate"),
        record.get("drawDate"),
    ]
    for raw_value in raw_candidates:
        if not isinstance(raw_value, str) or not raw_value.strip():
            continue
        parsed = _parse_datetime(raw_value.strip())
        if parsed is None:
            continue
        if keep_time:
            return parsed.strftime(f"{_DRAW_DATE_FORMAT} %H:%M")
        return parsed.strftime(_DRAW_DATE_FORMAT)
    return None


def _parse_datetime(raw_value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        pass
    for pattern in (
        "%a, %b %d, %Y %H:%M",
        "%a, %b %d, %Y %I:%M %p",
        _DRAW_DATE_FORMAT,
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(raw_value, pattern)
        except ValueError:
            continue
    return None


def _format_number(number: int) -> str:
    return f"{number:02d}"


def _int_value(raw_value: object) -> int | None:
    if isinstance(raw_value, bool) or raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
