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

_CALIFORNIA_DRAW_DATE_RE = re.compile(
    r"([A-Z]{3})/([A-Z]{3}) (\d{1,2}), (\d{4})"
    r"(?: - (EVENING|MIDDAY))?(?: \| Draw #(\d+))?"
)

_CALIFORNIA_GAME_SLUGS = {
    "powerball",
    "mega-millions",
    "superlotto-plus",
    "fantasy-5",
    "daily-4",
    "daily-3",
    "daily-derby",
}

_CALIFORNIA_BACKFILL_PAGE_SIZE = 50

_CALIFORNIA_HOT_SPOT_BACKFILL_COUNT = 300

_CALIFORNIA_SPECIAL_NUMBER_NAMES = {
    "powerball": "Powerball",
    "mega-millions": "Mega Ball",
    "superlotto-plus": "Superball",
}

def parse_california_daily3(raw_html: str) -> tuple[ParsedDraw, ...]:
    return parse_california_draw_game(raw_html)

def parse_california_draw_game(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        match = _CALIFORNIA_DRAW_DATE_RE.fullmatch(lines[index])
        if match is None:
            index += 1
            continue
        draw_date = _california_draw_date(match)
        numbers: list[str] = []
        cursor = index + 1
        while cursor < len(lines):
            line = lines[cursor]
            if _CALIFORNIA_DRAW_DATE_RE.fullmatch(line) is not None and numbers:
                break
            if _is_california_detail_boundary(line):
                break
            if _is_california_winning_number_line(line):
                number = _normalize_california_winning_number(line)
                if (
                    re.fullmatch(r"\d{1,2}", line)
                    and cursor + 1 < len(lines)
                    and lines[cursor + 1] in {"Powerball", "Mega Ball", "Mega"}
                ):
                    number = f"{line} {lines[cursor + 1]}"
                    cursor += 1
                numbers.append(number)
            cursor += 1
        prizes = _parse_california_prizes(lines[cursor:])
        if numbers:
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(numbers),
                    prizes=prizes,
                )
            )
        index = cursor
    return tuple(draws)

def parse_california_hot_spot(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draw_date = _parse_california_hot_spot_draw_date(soup)
    numbers = _parse_california_hot_spot_numbers(soup)
    if draw_date is None or not numbers:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(numbers),
            prizes=(),
        ),
    )

def parse_california_past_results_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("PreviousDraws") or ():
        draw = _parse_california_api_draw(item, game_slug)
        if draw is not None:
            draws.append(draw)
    return tuple(draws)

def parse_california_hot_spot_backfill_json(raw_json: str) -> tuple[ParsedDraw, ...]:
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("draws") or ():
        draw_date = _california_api_draw_datetime(
            item.get("DrawCloseTime"),
            include_time=True,
        )
        numbers = [
            f"{number['Number']} Bulls-eye"
            if number.get("IsBullseye")
            else str(number["Number"])
            for number in item.get("WinningNumbers") or ()
            if number.get("Number") is not None
        ]
        if draw_date is not None and numbers:
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(numbers),
                    prizes=(),
                )
            )
    return tuple(draws)

def _is_california_detail_boundary(line: str) -> bool:
    return line in {
        "Detailed Draw Results",
        "Detailed Draw Results for California",
        "Matching Numbers Winning Tickets Prize Amounts",
    }

def _is_california_winning_number_line(line: str) -> bool:
    if line in {"Winning Numbers:", "Winning Numbers"}:
        return False
    if line.startswith("Draw #"):
        return False
    if line == "* * *":
        return False
    if re.fullmatch(r"\d{1,2}(?: (?:Powerball|Mega Ball|Mega))?", line):
        return True
    return bool(
        re.fullmatch(
            r"(?:First|Second|Third): \d{2} - .+|Race Time: \d:\d{2}\.\d{2}",
            line,
        )
    )

def _normalize_california_winning_number(line: str) -> str:
    return line.strip()

def _parse_california_prizes(lines: list[str]) -> tuple[PrizeRow, ...]:
    prizes: list[PrizeRow] = []
    for line in lines:
        if _CALIFORNIA_DRAW_DATE_RE.fullmatch(line) is not None:
            break
        if line.startswith(("This page", "Past Winning Numbers", "How to claim")):
            break
        prize_match = re.fullmatch(r"(.+?) ([\d,]+) \$([\d,.]+)", line)
        if prize_match is None:
            continue
        winners = _int_from_text(prize_match.group(2))
        prize = _money_to_float(prize_match.group(3))
        prizes.append(
            PrizeRow(
                prize_amount=prize,
                wa_winners=winners,
                total=winners * prize,
            )
        )
    return tuple(prizes)

def _parse_california_hot_spot_draw_date(soup: BeautifulSoup) -> str | None:
    date_node = soup.select_one(".htspt__cards--next-draw-date .caps-texts")
    container = soup.select_one(".htspt__cards--next-draw-date")
    if date_node is None or container is None:
        return None
    time_nodes = container.find_all("strong")
    if len(time_nodes) < 2:
        return None
    parsed_date = datetime.strptime(date_node.get_text(" ", strip=True), "%B %d, %Y")
    raw_time = time_nodes[1].get_text(" ", strip=True)
    parsed_time = datetime.strptime(raw_time.replace(".", "").upper(), "%I:%M %p")
    display_time = parsed_time.strftime("%I:%M %p").lstrip("0")
    return f"{parsed_date.strftime(_DRAW_DATE_FORMAT)} {display_time}"

def _parse_california_hot_spot_numbers(soup: BeautifulSoup) -> tuple[str, ...]:
    items = soup.select(".sr-only-container .sr-only li")
    numbers: list[str] = []
    for item in items:
        text = item.get_text(" ", strip=True)
        if text == "Draw Results:":
            continue
        if match := re.fullmatch(r"Bulls-eye number is\s+(\d{1,2})", text):
            numbers.append(f"{match.group(1)} Bulls-eye")
        elif re.fullmatch(r"\d{1,2}", text):
            numbers.append(text)
    return tuple(numbers)

def _parse_california_past_results_config(
    raw_html: str,
    game_slug: str,
) -> tuple[str, int, int]:
    soup = BeautifulSoup(raw_html, "html.parser")
    for script in soup.select(".past-winning-numbers script"):
        text = script.string or script.get_text("", strip=True)
        if '"drawGamePastDrawResultsApi"' not in text:
            continue
        config = json.loads(text)
        return (
            str(config["drawGamePastDrawResultsApi"]),
            int(config["pwnGameId"]),
            int(config.get("pwnTotalResults") or 0),
        )
    raise ValueError(f"California backfill metadata not found for {game_slug}")

def _parse_california_api_draw(
    item: dict[str, object],
    game_slug: str,
) -> ParsedDraw | None:
    draw_date = _california_api_draw_datetime(item.get("DrawDate"))
    if draw_date is None:
        return None
    if game_slug == "daily-3":
        draw_number = _int_value(item.get("DrawNumber"))
        if draw_number is not None:
            session = "Evening" if draw_number % 2 else "Midday"
            draw_date = f"{draw_date} {session}"

    numbers = _california_api_winning_numbers(item, game_slug)
    if not numbers:
        return None
    return ParsedDraw(
        draw_date=draw_date,
        winning_number=", ".join(numbers),
        prizes=_california_api_prizes(item),
    )

def _california_api_draw_datetime(
    raw_value: object,
    *,
    include_time: bool = False,
) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    display = parsed.strftime(_DRAW_DATE_FORMAT)
    if not include_time:
        return display
    display_time = parsed.strftime("%I:%M %p").lstrip("0")
    return f"{display} {display_time}"

def _california_api_winning_numbers(
    item: dict[str, object],
    game_slug: str,
) -> tuple[str, ...]:
    number_items = _ordered_api_values(item.get("WinningNumbers"))
    if game_slug == "daily-derby":
        horse_labels = ("First", "Second", "Third")
        numbers = []
        for label, number_item in zip(horse_labels, number_items, strict=False):
            number = str(number_item.get("Number", "")).zfill(2)
            name = number_item.get("Name")
            if name:
                numbers.append(f"{label}: {number} - {name}")
            else:
                numbers.append(f"{label}: {number}")
        race_time = item.get("RaceTime")
        if race_time:
            numbers.append(f"Race Time: {race_time}")
        return tuple(numbers)

    numbers: list[str] = []
    for number_item in number_items:
        number = number_item.get("Number")
        if number is None:
            continue
        text = str(number)
        if number_item.get("IsSpecial"):
            name = _CALIFORNIA_SPECIAL_NUMBER_NAMES.get(game_slug)
            if name:
                text = f"{text} {name}"
        numbers.append(text)
    return tuple(numbers)

def _california_api_prizes(item: dict[str, object]) -> tuple[PrizeRow, ...]:
    prizes: list[PrizeRow] = []
    for prize_item in _ordered_api_values(item.get("Prizes")):
        amount = _float_value(prize_item.get("Amount"))
        winners = _int_value(prize_item.get("Count")) or 0
        total = _float_value(prize_item.get("TotalPayout"))
        if total == 0:
            total = winners * amount
        prizes.append(
            PrizeRow(
                prize_amount=amount,
                wa_winners=winners,
                total=total,
            )
        )
    return tuple(prizes)

def _ordered_api_values(raw_value: object) -> tuple[dict[str, object], ...]:
    if isinstance(raw_value, dict):
        return tuple(
            value
            for _, value in sorted(
                raw_value.items(),
                key=lambda item: (
                    0,
                    int(item[0]),
                )
                if str(item[0]).isdigit()
                else (1, str(item[0])),
            )
            if isinstance(value, dict)
        )
    if isinstance(raw_value, list):
        return tuple(value for value in raw_value if isinstance(value, dict))
    return ()

def _california_draw_date(match: re.Match[str]) -> str:
    parsed = datetime.strptime(
        f"{match.group(1).title()}, {match.group(2).title()} {match.group(3)}, {match.group(4)}",
        _DRAW_DATE_FORMAT,
    )
    session = match.group(5)
    if session is None:
        return parsed.strftime(_DRAW_DATE_FORMAT)
    return f"{parsed.strftime(_DRAW_DATE_FORMAT)} {session.title()}"
