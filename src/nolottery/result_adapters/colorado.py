from __future__ import annotations

import json
import re
import ssl
from dataclasses import dataclass
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

@dataclass(frozen=True)
class _ColoradoGameSpec:
    numbers_label: str
    primary_count: int
    special_number_name: str | None = None


_COLORADO_DRAWING_HISTORY_GAMES = {
    "colorado-cash-5": _ColoradoGameSpec("Cash 5 Numbers", 5),
    "colorado-lotto-plus": _ColoradoGameSpec("Colorado Lotto+ Numbers", 6),
    "colorado-pick-3": _ColoradoGameSpec("Pick 3 Numbers", 3),
    "mega-millions": _ColoradoGameSpec("Mega Millions Numbers", 5, "Mega Ball"),
    "millionaire-for-life": _ColoradoGameSpec(
        "Millionaire for Life Numbers",
        5,
        "Life Ball",
    ),
    "powerball": _ColoradoGameSpec("Powerball Numbers", 5, "Powerball"),
}


def fetch_colorado_backfill_result(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    raw_html, source_url = read_source(
        game.source_url,
        source_dir,
        f"{game.slug}-co-backfill",
    )
    draws = parse_colorado_drawing_history(raw_html, game.slug)
    snapshots = [SourceSnapshot(source_url, raw_html, draws)]
    all_draws = list(draws)

    month_urls = _colorado_month_urls(raw_html, source_url)
    for month_url in month_urls[1:]:
        month_token = _colorado_month_token(month_url)
        raw_month_html, month_source_url = read_source(
            month_url,
            source_dir,
            f"{game.slug}-co-backfill-{month_token}",
        )
        month_draws = parse_colorado_drawing_history(raw_month_html, game.slug)
        snapshots.append(SourceSnapshot(month_source_url, raw_month_html, month_draws))
        all_draws.extend(month_draws)

    return AdapterFetch(
        source_url=source_url,
        draws=tuple(all_draws),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def parse_colorado_drawing_history(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    spec = _COLORADO_DRAWING_HISTORY_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    structured_draws = _parse_structured_colorado_drawings(soup, spec)
    if structured_draws:
        return structured_draws
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        draw_date = _colorado_draw_date(lines[index])
        if draw_date is None:
            index += 1
            continue
        cursor = index + 1
        while cursor < len(lines) and lines[cursor] != spec.numbers_label:
            if _colorado_draw_date(lines[cursor]) is not None:
                break
            cursor += 1
        if cursor + 1 >= len(lines) or lines[cursor] != spec.numbers_label:
            index += 1
            continue
        numbers = re.findall(r"\d{1,2}", lines[cursor + 1])
        if len(numbers) != spec.primary_count:
            index += 1
            continue
        if spec.special_number_name is None:
            winning_number = ", ".join(numbers)
            next_index = cursor + 2
        else:
            if cursor + 2 >= len(lines):
                index += 1
                continue
            special_number = re.fullmatch(r"\d{1,2}", lines[cursor + 2])
            if special_number is None:
                index += 1
                continue
            winning_number = ", ".join(
                (
                    *numbers,
                    f"{special_number.group(0)} {spec.special_number_name}",
                )
            )
            next_index = cursor + 3
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
        index = next_index
    return tuple(draws)


def _parse_structured_colorado_drawings(
    soup: BeautifulSoup,
    spec: _ColoradoGameSpec,
) -> tuple[ParsedDraw, ...]:
    draws: list[ParsedDraw] = []
    for drawing in soup.select(".recent-drawings .drawing"):
        date_element = drawing.select_one(".date")
        if date_element is None:
            continue
        draw_date = _colorado_draw_date(date_element.get_text(" ", strip=True))
        if draw_date is None:
            continue
        for draw in drawing.select(".draws > .draw"):
            title = draw.select_one("p.title")
            if title is None or title.get_text(" ", strip=True) != spec.numbers_label:
                continue
            numbers = tuple(
                span.get_text(strip=True)
                for span in draw.select("p.draw span")
            )
            if len(numbers) != spec.primary_count:
                continue
            if spec.special_number_name is None:
                winning_number = ", ".join(numbers)
            else:
                special = draw.select_one("p.extra span")
                if special is None:
                    continue
                winning_number = ", ".join(
                    (
                        *numbers,
                        f"{special.get_text(strip=True)} {spec.special_number_name}",
                    )
                )
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=winning_number,
                    prizes=(),
                )
            )
    return tuple(draws)


def _colorado_month_urls(raw_html: str, source_url: str) -> tuple[str, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    urls: list[str] = []
    for option in soup.select("option[value]"):
        value = option.get("value")
        if not isinstance(value, str):
            continue
        if re.search(r"/drawings/\d{4}-\d{2}/?$", value) is None:
            continue
        month_url = urljoin(source_url, value)
        if month_url not in urls:
            urls.append(month_url)
    return tuple(urls)


def _colorado_month_token(month_url: str) -> str:
    match = re.search(r"/drawings/(\d{4}-\d{2})/?$", month_url)
    if match is None:
        return "month"
    return match.group(1)


def _colorado_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A, %m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        pass
    match = re.fullmatch(
        r"([A-Z][a-z]{2})\. (\d{1,2}), (\d{4}): (Midday|Evening)",
        raw_value,
    )
    if match is None:
        return None
    try:
        parsed = datetime.strptime(
            f"{match.group(1)} {match.group(2)}, {match.group(3)}",
            "%b %d, %Y",
        )
    except ValueError:
        return None
    return f"{parsed.strftime(_DRAW_DATE_FORMAT)} {match.group(4)}"
