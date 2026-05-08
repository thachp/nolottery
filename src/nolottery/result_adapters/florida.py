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

_FLORIDA_HISTORY_GAMES = {
    "cash4life": "https://files.floridalottery.com/exptkt/c4l.pdf",
    "florida-cash-pop": "https://files.floridalottery.com/exptkt/cp.pdf",
    "florida-fantasy-5": "https://files.floridalottery.com/exptkt/ff.pdf",
    "florida-lotto": "https://files.floridalottery.com/exptkt/l6.pdf",
    "jackpot-triple-play": "https://files.floridalottery.com/exptkt/jtp.pdf",
    "mega-millions": "https://files.floridalottery.com/exptkt/mmil.pdf",
    "powerball": "https://files.floridalottery.com/exptkt/pb.pdf",
    **{game_slug: url for game_slug, (url, _) in _FLORIDA_PICK_GAMES.items()},
}

_CASH_POP_SESSIONS = ("Morning", "Matinee", "Afternoon", "Evening", "Late Night")

def _florida_history_draws(
    game_slug: str,
    *,
    source_dir: Path | None,
) -> tuple[str, str, tuple[ParsedDraw, ...]]:
    raw_text, source_url = _read_florida_history_source(game_slug, source_dir)
    return raw_text, source_url, parse_florida_history_text(raw_text, game_slug)


def parse_florida_history_text(
    raw_text: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if game_slug in _FLORIDA_PICK_GAMES:
        return parse_florida_pick_history_text(raw_text, game_slug)
    if game_slug == "florida-cash-pop":
        return _parse_florida_cash_pop_history(raw_text)
    if game_slug == "florida-fantasy-5":
        return _parse_florida_draw_type_history(raw_text, 5)
    if game_slug == "cash4life":
        return _parse_florida_extra_ball_history(raw_text, "CB", "Cash Ball")
    if game_slug == "mega-millions":
        return _parse_florida_extra_ball_history(raw_text, "MB", "Mega Ball")
    if game_slug == "powerball":
        return _parse_florida_powerball_history(raw_text)
    if game_slug in {"florida-lotto", "jackpot-triple-play"}:
        return _parse_florida_six_number_history(raw_text, game_slug)
    return ()


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


def _parse_florida_cash_pop_history(raw_text: str) -> tuple[ParsedDraw, ...]:
    entry_re = re.compile(
        r"(?P<date>\d{1,2}/\d{1,2}/\d{4})\s+"
        r"(?P<morning>\d{1,2})\s+"
        r"(?P<matinee>\d{1,2})\s+"
        r"(?P<afternoon>\d{1,2})\s+"
        r"(?P<evening>\d{1,2})\s+"
        r"(?P<late_night>\d{1,2})"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        draw_date = _format_florida_history_date(match.group("date"))
        values = (
            match.group("morning"),
            match.group("matinee"),
            match.group("afternoon"),
            match.group("evening"),
            match.group("late_night"),
        )
        for session, value in zip(_CASH_POP_SESSIONS, values, strict=True):
            draws.append(
                ParsedDraw(
                    draw_date=f"{draw_date} {session}",
                    winning_number=value,
                    prizes=(),
                )
            )
    return tuple(draws)


def _parse_florida_draw_type_history(
    raw_text: str,
    number_count: int,
) -> tuple[ParsedDraw, ...]:
    number_pattern = r"\d{1,2}" + (r"\s+\d{1,2}" * (number_count - 1))
    entry_re = re.compile(
        rf"(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{2}})\s+"
        rf"(?P<session>EVENING|MIDDAY)\s+"
        rf"(?P<numbers>{number_pattern})"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        session = "Evening" if match.group("session") == "EVENING" else "Midday"
        numbers = re.findall(r"\d{1,2}", match.group("numbers"))
        draws.append(
            ParsedDraw(
                draw_date=(
                    f"{_format_florida_history_date(match.group('date'))} {session}"
                ),
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)


def _parse_florida_extra_ball_history(
    raw_text: str,
    marker: str,
    label: str,
) -> tuple[ParsedDraw, ...]:
    entry_re = re.compile(
        rf"(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{2}})\s+"
        rf"(?P<numbers>{_hyphenated_numbers_pattern(5)})\s+"
        rf"{marker}\s*(?P<extra>\d{{1,2}})"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        numbers = _numbers_from_hyphenated(match.group("numbers"))
        numbers.append(f"{match.group('extra')} {label}")
        draws.append(
            ParsedDraw(
                draw_date=_format_florida_history_date(match.group("date")),
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)


def _parse_florida_powerball_history(raw_text: str) -> tuple[ParsedDraw, ...]:
    entry_re = re.compile(
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2})\s+"
        r"(?P<numbers>(?:\d{1,2}\s+){5})"
        r"PB\s*(?P<extra>\d{1,2})"
        r"(?:\s+X\d+)?\s+POWERBALL(?!\s+DP)"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        numbers = re.findall(r"\d{1,2}", match.group("numbers"))
        numbers.append(f"{match.group('extra')} Powerball")
        draws.append(
            ParsedDraw(
                draw_date=_format_florida_history_date(match.group("date")),
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)


def _parse_florida_six_number_history(
    raw_text: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    entry_re = re.compile(
        rf"(?P<date>\d{{1,2}}/\d{{1,2}}/\d{{2}})\s+"
        rf"(?P<numbers>{_hyphenated_numbers_pattern(6)})"
        rf"(?:\s+(?P<label>LOTTO)(?!\s+DP))?"
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        if game_slug == "florida-lotto" and match.group("label") != "LOTTO":
            continue
        draws.append(
            ParsedDraw(
                draw_date=_format_florida_history_date(match.group("date")),
                winning_number=", ".join(
                    _numbers_from_hyphenated(match.group("numbers"))
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _hyphenated_numbers_pattern(number_count: int) -> str:
    return r"\d{1,2}" + (r"\s*-\s*\d{1,2}" * (number_count - 1))


def _numbers_from_hyphenated(raw_numbers: str) -> list[str]:
    return re.findall(r"\d{1,2}", raw_numbers)


def _format_florida_history_date(raw_date: str) -> str:
    date_format = (
        "%m/%d/%Y" if len(raw_date.rsplit("/", 1)[-1]) == 4 else "%m/%d/%y"
    )
    return datetime.strptime(raw_date, date_format).strftime(_DRAW_DATE_FORMAT)


def _read_florida_history_source(
    game_slug: str,
    source_dir: Path | None,
) -> tuple[str, str]:
    history_url = _FLORIDA_HISTORY_GAMES[game_slug]
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
