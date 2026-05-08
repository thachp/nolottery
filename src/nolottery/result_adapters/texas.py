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
class _TexasGameSpec:
    primary_count: int
    special_number_name: str | None = None
    numbers_column: int = 1
    session_column: int | None = None
    session_columns: tuple[tuple[str, int, int], ...] = ()


_TEXAS_WINNING_NUMBER_GAMES = {
    "mega-millions": _TexasGameSpec(5, "Mega Ball"),
    "powerball": _TexasGameSpec(5, "Powerball"),
    "texas-all-or-nothing": _TexasGameSpec(12, numbers_column=2, session_column=1),
    "texas-cash-five": _TexasGameSpec(5),
    "texas-daily-4": _TexasGameSpec(
        4,
        "Fire Ball",
        session_columns=(
            ("Morning", 1, 2),
            ("Day", 3, 4),
            ("Evening", 5, 6),
            ("Night", 7, 8),
        ),
    ),
    "texas-lotto": _TexasGameSpec(6),
    "texas-pick-3": _TexasGameSpec(
        3,
        "Fire Ball",
        session_columns=(
            ("Morning", 1, 2),
            ("Day", 3, 4),
            ("Evening", 5, 6),
            ("Night", 7, 8),
        ),
    ),
    "texas-two-step": _TexasGameSpec(4, "Bonus Ball"),
}

def parse_texas_winning_numbers(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    spec = _TEXAS_WINNING_NUMBER_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) < 2:
            continue
        draw_date = _texas_draw_date(cells[0])
        if draw_date is None:
            continue
        if spec.session_columns:
            draws.extend(_texas_session_draws(cells, draw_date, spec))
            continue
        if spec.numbers_column >= len(cells):
            continue
        numbers = re.findall(r"\d{1,2}", cells[spec.numbers_column])
        if len(numbers) != spec.primary_count:
            continue
        draw_time = cells[spec.session_column] if spec.session_column is not None else ""
        display_date = f"{draw_date} {draw_time}".strip()
        if spec.special_number_name is None:
            winning_number = ", ".join(numbers)
        elif len(cells) < 3:
            continue
        else:
            special_number = re.search(r"\d{1,2}", cells[2])
            if special_number is None:
                continue
            winning_number = ", ".join(
                [
                    *numbers,
                    f"{special_number.group(0)} {spec.special_number_name}",
                ]
            )
        draws.append(
            ParsedDraw(
                draw_date=display_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
    return tuple(draws)


def _texas_session_draws(
    cells: list[str],
    draw_date: str,
    spec: _TexasGameSpec,
) -> tuple[ParsedDraw, ...]:
    draws: list[ParsedDraw] = []
    for session, numbers_column, special_column in spec.session_columns:
        if max(numbers_column, special_column) >= len(cells):
            continue
        numbers = re.findall(r"\d{1,2}", cells[numbers_column])
        special_number = re.search(r"\d{1,2}", cells[special_column])
        if len(numbers) != spec.primary_count or special_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=f"{draw_date} {session}",
                winning_number=", ".join(
                    [
                        *numbers,
                        f"{special_number.group(0)} {spec.special_number_name}",
                    ]
                ),
                prizes=(),
            )
        )
    return tuple(draws)

def _texas_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None
