from __future__ import annotations

import json
import re
import sqlite3
import ssl
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from math import ceil
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import httpx
import pdfplumber
from bs4 import BeautifulSoup, Tag

from .db import DEFAULT_JURISDICTION_CODE
from .metadata import GameMetadata

_DRAW_DATE_FORMAT = "%a, %b %d, %Y"
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
_FLORIDA_PICK_GAMES = {
    "florida-pick-2": ("https://files.floridalottery.com/exptkt/p2.pdf", 2),
    "florida-pick-3": ("https://files.floridalottery.com/exptkt/p3.pdf", 3),
    "florida-pick-4": ("https://files.floridalottery.com/exptkt/p4.pdf", 4),
    "florida-pick-5": ("https://files.floridalottery.com/exptkt/p5.pdf", 5),
}
_NEW_YORK_DAILY_NUMBERS_URL = (
    "https://data.ny.gov/resource/hsys-3def.json?"
    "$limit=50000&$order=draw_date%20DESC"
)
_NEW_YORK_DAILY_GAMES = {"numbers", "win-4"}
_TEXAS_SPECIAL_NUMBER_NAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}


@dataclass(frozen=True)
class PrizeRow:
    prize_amount: float
    wa_winners: int
    total: float


@dataclass(frozen=True)
class ParsedDraw:
    draw_date: str
    winning_number: str
    prizes: tuple[PrizeRow, ...]


@dataclass(frozen=True)
class FetchResult:
    game_name: str
    source_url: str
    draw_count: int
    prize_row_count: int
    page_count: int = 1


def fetch_game(
    conn: sqlite3.Connection,
    game: GameMetadata,
    source_file: Path | None = None,
    jurisdiction_code: str = DEFAULT_JURISDICTION_CODE,
) -> FetchResult:
    if (
        source_file is None
        and jurisdiction_code == "fl"
        and game.slug in _FLORIDA_PICK_GAMES
    ):
        raw_html, source_url, draws = _florida_pick_history_draws(
            game.slug,
            source_dir=None,
        )
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_html, draws)
        new_draws = _filter_newer_draws(conn, jurisdiction_code, game.slug, draws)
        _insert_draw_results(conn, jurisdiction_code, game.slug, new_draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(new_draws),
            prize_row_count=sum(len(draw.prizes) for draw in new_draws),
        )
    if (
        source_file is None
        and jurisdiction_code == "ny"
        and game.slug in _NEW_YORK_DAILY_GAMES
    ):
        raw_json, source_url = _read_source(
            _NEW_YORK_DAILY_NUMBERS_URL,
            None,
            f"{game.slug}-ny-backfill",
            suffix=".json",
        )
        draws = parse_new_york_daily_numbers_json(raw_json, game.slug)
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_json, draws)
        new_draws = _filter_newer_draws(conn, jurisdiction_code, game.slug, draws)
        _insert_draw_results(conn, jurisdiction_code, game.slug, new_draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(new_draws),
            prize_row_count=sum(len(draw.prizes) for draw in new_draws),
        )

    if source_file is not None:
        raw_html = source_file.read_text(encoding="utf-8")
        source_url = source_file.as_uri()
    else:
        raw_html, source_url = _read_source(game.source_url, None, game.slug)

    draws = _parse_draws(raw_html, jurisdiction_code, game.slug)
    _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_html, draws)
    new_draws = _filter_newer_draws(conn, jurisdiction_code, game.slug, draws)
    _insert_draw_results(conn, jurisdiction_code, game.slug, new_draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=source_url,
        draw_count=len(new_draws),
        prize_row_count=sum(len(draw.prizes) for draw in new_draws),
    )


def fetch_game_backfill(
    conn: sqlite3.Connection,
    game: GameMetadata,
    source_dir: Path | None = None,
    jurisdiction_code: str = DEFAULT_JURISDICTION_CODE,
) -> FetchResult:
    if jurisdiction_code == "fl" and game.slug in _FLORIDA_PICK_GAMES:
        raw_html, source_url, draws = _florida_pick_history_draws(
            game.slug,
            source_dir=source_dir,
        )
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_html, draws)
        _replace_draw_results(conn, jurisdiction_code, game.slug, draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(draws),
            prize_row_count=sum(len(draw.prizes) for draw in draws),
            page_count=1,
        )
    if jurisdiction_code == "ny" and game.slug in _NEW_YORK_DAILY_GAMES:
        raw_json, source_url = _read_source(
            _NEW_YORK_DAILY_NUMBERS_URL,
            source_dir,
            f"{game.slug}-ny-backfill",
            suffix=".json",
        )
        draws = parse_new_york_daily_numbers_json(raw_json, game.slug)
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_json, draws)
        _replace_draw_results(conn, jurisdiction_code, game.slug, draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(draws),
            prize_row_count=sum(len(draw.prizes) for draw in draws),
            page_count=1,
        )
    if jurisdiction_code == "tx" and game.slug in _TEXAS_SPECIAL_NUMBER_NAMES:
        raw_html, source_url = _read_source(game.source_url, source_dir, game.slug)
        draws = parse_texas_winning_numbers(raw_html, game.slug)
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_html, draws)
        _replace_draw_results(conn, jurisdiction_code, game.slug, draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(draws),
            prize_row_count=sum(len(draw.prizes) for draw in draws),
            page_count=1,
        )

    discovery_html, discovery_url = _read_source(game.source_url, source_dir, game.slug)
    if jurisdiction_code == "ca":
        return _fetch_california_backfill(
            conn,
            game,
            discovery_html,
            discovery_url,
            source_dir,
            jurisdiction_code,
        )

    years = parse_available_years(discovery_html)
    if not years:
        years = (datetime.now(tz=UTC).year,)

    all_draws: list[ParsedDraw] = []
    page_count = 0
    for year in years:
        year_url = _year_url(game.source_url, year)
        raw_html, source_url = _read_source(
            year_url,
            source_dir,
            f"{game.slug}-{year}",
        )
        draws = _parse_draws(raw_html, jurisdiction_code, game.slug)
        all_draws.extend(draws)
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_html, draws)
        page_count += 1

    deduped_draws = _dedupe_draws(tuple(all_draws))
    _replace_draw_results(conn, jurisdiction_code, game.slug, deduped_draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=discovery_url,
        draw_count=len(deduped_draws),
        prize_row_count=sum(len(draw.prizes) for draw in deduped_draws),
        page_count=page_count,
    )


def _fetch_california_backfill(
    conn: sqlite3.Connection,
    game: GameMetadata,
    discovery_html: str,
    discovery_url: str,
    source_dir: Path | None,
    jurisdiction_code: str,
) -> FetchResult:
    if game.slug == "hot-spot":
        return _fetch_california_hot_spot_backfill(
            conn,
            game,
            discovery_url,
            source_dir,
            jurisdiction_code,
        )

    api_path, game_id, configured_total = _parse_california_past_results_config(
        discovery_html,
        game.slug,
    )
    all_draws: list[ParsedDraw] = []
    page_count = 0
    page = 1
    total_results = configured_total

    while True:
        api_url = urljoin(
            game.source_url,
            f"{api_path}{game_id}/{page}/{_CALIFORNIA_BACKFILL_PAGE_SIZE}",
        )
        raw_json, source_url = _read_source(
            api_url,
            source_dir,
            f"{game.slug}-ca-backfill-{page}",
            suffix=".json",
        )
        payload = json.loads(raw_json)
        if payload is None:
            draws = ()
            _insert_snapshot(
                conn,
                jurisdiction_code,
                game.slug,
                source_url,
                raw_json,
                draws,
            )
            page_count += 1
            break
        total_results = int(payload.get("TotalPreviousDraws") or total_results or 0)
        draws = parse_california_past_results_json(raw_json, game.slug)
        all_draws.extend(draws)
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_json, draws)
        page_count += 1

        total_pages = ceil(total_results / _CALIFORNIA_BACKFILL_PAGE_SIZE)
        if page >= total_pages or len(draws) < _CALIFORNIA_BACKFILL_PAGE_SIZE:
            break
        page += 1

    deduped_draws = _dedupe_draws(tuple(all_draws))
    _replace_draw_results(conn, jurisdiction_code, game.slug, deduped_draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=discovery_url,
        draw_count=len(deduped_draws),
        prize_row_count=sum(len(draw.prizes) for draw in deduped_draws),
        page_count=page_count,
    )


def _fetch_california_hot_spot_backfill(
    conn: sqlite3.Connection,
    game: GameMetadata,
    discovery_url: str,
    source_dir: Path | None,
    jurisdiction_code: str,
) -> FetchResult:
    source_url = "https://www.calottery.com/api/v1.5/drawgames/22"
    api_url = f"{source_url}?drawscount={_CALIFORNIA_HOT_SPOT_BACKFILL_COUNT}"
    raw_json, resolved_url = _read_source(
        api_url,
        source_dir,
        f"{game.slug}-ca-backfill-1",
        suffix=".json",
    )
    draws = parse_california_hot_spot_backfill_json(raw_json)
    _insert_snapshot(conn, jurisdiction_code, game.slug, resolved_url, raw_json, draws)
    _replace_draw_results(conn, jurisdiction_code, game.slug, draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=discovery_url,
        draw_count=len(draws),
        prize_row_count=sum(len(draw.prizes) for draw in draws),
        page_count=1,
    )


def _florida_pick_history_draws(
    game_slug: str,
    *,
    source_dir: Path | None,
) -> tuple[str, str, tuple[ParsedDraw, ...]]:
    raw_text, source_url = _read_florida_pick_history_source(game_slug, source_dir)
    return raw_text, source_url, parse_florida_pick_history_text(raw_text, game_slug)


def parse_past_drawings(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.table-viewport-large"):
        draw = _parse_large_table(table)
        if draw is not None:
            draws.append(draw)
    return tuple(draws)


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


def parse_texas_winning_numbers(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _TEXAS_SPECIAL_NUMBER_NAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) < 3:
            continue
        draw_date = _texas_draw_date(cells[0])
        if draw_date is None:
            continue
        numbers = re.findall(r"\d{1,2}", cells[1])
        special_number = re.search(r"\d{1,2}", cells[2])
        if len(numbers) != 5 or special_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number.group(0)} {special_number_name}"]
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


def _new_york_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    return datetime.fromisoformat(raw_value).strftime(_DRAW_DATE_FORMAT)


def _page_lines(soup: BeautifulSoup) -> list[str]:
    return [
        line.strip()
        for line in soup.get_text("\n", strip=True).splitlines()
        if line.strip()
    ]


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


def _int_value(raw_value: object) -> int | None:
    if isinstance(raw_value, bool) or raw_value is None:
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _float_value(raw_value: object) -> float:
    if isinstance(raw_value, bool) or raw_value is None:
        return 0.0
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def _parse_draws(
    raw_html: str,
    jurisdiction_code: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if jurisdiction_code == "ca" and game_slug == "hot-spot":
        return parse_california_hot_spot(raw_html)
    if jurisdiction_code == "ca" and game_slug in _CALIFORNIA_GAME_SLUGS:
        return parse_california_draw_game(raw_html)
    if jurisdiction_code == "tx" and game_slug in _TEXAS_SPECIAL_NUMBER_NAMES:
        return parse_texas_winning_numbers(raw_html, game_slug)
    return parse_past_drawings(raw_html)


def parse_available_years(raw_html: str) -> tuple[int, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    years: list[int] = []
    for option in soup.select('option[value$=" year"]'):
        value = option.get("value", "")
        match = re.fullmatch(r"(\d{4}) year", value.strip())
        if match is not None:
            years.append(int(match.group(1)))
    return tuple(dict.fromkeys(years))


def _parse_large_table(table: Tag) -> ParsedDraw | None:
    date_node = table.select_one("thead .h2-like")
    ball_cell = table.select_one("td.game-balls")
    ball_nodes = ball_cell.select("li") if ball_cell is not None else []
    body_rows = table.select("tbody > tr")
    if date_node is None or not ball_nodes or not body_rows:
        return None

    prizes: list[PrizeRow] = []
    for row in body_rows:
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if cells and row.select_one("td.game-balls"):
            cells = cells[1:]
        if len(cells) < 3:
            continue
        if "$" not in cells[0]:
            continue
        prizes.append(
            PrizeRow(
                prize_amount=_money_to_float(cells[0]),
                wa_winners=_int_from_text(cells[1]),
                total=_money_to_float(cells[2]),
            )
        )

    return ParsedDraw(
        draw_date=date_node.get_text(" ", strip=True),
        winning_number=", ".join(
            ball_node.get_text(" ", strip=True) for ball_node in ball_nodes
        ),
        prizes=tuple(prizes),
    )


def _read_source(
    source_url: str,
    source_dir: Path | None,
    source_name: str,
    *,
    suffix: str = ".html",
) -> tuple[str, str]:
    if source_dir is None:
        response = httpx.get(source_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        return response.text, str(response.url)

    source_file = source_dir / f"{source_name}{suffix}"
    return source_file.read_text(encoding="utf-8"), source_file.as_uri()


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


def _extract_pdf_text(raw_pdf: bytes) -> str:
    with pdfplumber.open(BytesIO(raw_pdf)) as pdf:
        return "\n".join(
            page.extract_text(layout=True, x_tolerance=1, y_tolerance=3) or ""
            for page in pdf.pages
        )


def _year_url(source_url: str, year: int) -> str:
    parsed = urlparse(source_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["unitcount"] = str(year)
    query["unittype"] = "year"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _insert_snapshot(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    source_url: str,
    raw_html: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    parsed_json = json.dumps([asdict(draw) for draw in draws], sort_keys=True)
    fetched_at = datetime.now(tz=UTC).isoformat()
    conn.execute(
        """
        insert into fetch_snapshots (
            jurisdiction_code,
            game_slug,
            source_url,
            fetched_at,
            raw_html,
            parsed_json
        )
        values (?, ?, ?, ?, ?, ?)
        """,
        (jurisdiction_code, game_slug, source_url, fetched_at, raw_html, parsed_json),
    )


def _dedupe_draws(draws: tuple[ParsedDraw, ...]) -> tuple[ParsedDraw, ...]:
    deduped: dict[tuple[str, str], ParsedDraw] = {}
    for draw in draws:
        deduped[(draw.draw_date, draw.winning_number)] = draw
    return tuple(deduped.values())


def _filter_newer_draws(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> tuple[ParsedDraw, ...]:
    latest_draw_date = _latest_stored_draw_date(conn, jurisdiction_code, game_slug)
    existing_keys = _existing_draw_keys(conn, jurisdiction_code, game_slug)

    newer_draws: list[ParsedDraw] = []
    seen_keys: set[tuple[str, str]] = set()
    for draw in draws:
        key = (draw.draw_date, draw.winning_number)
        parsed_draw_date = _parse_draw_date(draw.draw_date)
        if latest_draw_date is not None and parsed_draw_date is not None:
            if parsed_draw_date <= latest_draw_date:
                continue
        if key in existing_keys or key in seen_keys:
            continue
        newer_draws.append(draw)
        seen_keys.add(key)

    return tuple(newer_draws)


def _latest_stored_draw_date(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
) -> date | None:
    rows = conn.execute(
        """
        select distinct draw_date
        from draw_results
        where jurisdiction_code = ?
            and game_slug = ?
        """,
        (jurisdiction_code, game_slug),
    ).fetchall()
    parsed_dates = [
        parsed_date
        for row in rows
        if (parsed_date := _parse_draw_date(row["draw_date"])) is not None
    ]
    return max(parsed_dates, default=None)


def _existing_draw_keys(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
) -> set[tuple[str, str]]:
    rows = conn.execute(
        """
        select distinct draw_date, winning_number
        from draw_results
        where jurisdiction_code = ?
            and game_slug = ?
        """,
        (jurisdiction_code, game_slug),
    ).fetchall()
    return {(row["draw_date"], row["winning_number"]) for row in rows}


def _parse_draw_date(draw_date: str) -> date | None:
    try:
        return _parse_stored_draw_date(draw_date)
    except ValueError:
        return None


def _california_draw_date(match: re.Match[str]) -> str:
    parsed = datetime.strptime(
        f"{match.group(1).title()}, {match.group(2).title()} {match.group(3)}, {match.group(4)}",
        _DRAW_DATE_FORMAT,
    )
    session = match.group(5)
    if session is None:
        return parsed.strftime(_DRAW_DATE_FORMAT)
    return f"{parsed.strftime(_DRAW_DATE_FORMAT)} {session.title()}"


def _parse_stored_draw_date(draw_date: str) -> date:
    for session in (" Evening", " Midday"):
        if draw_date.endswith(session):
            draw_date = draw_date[: -len(session)]
            break
    if match := re.match(r"^([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{2}, \d{4}) ", draw_date):
        draw_date = match.group(1)
    return datetime.strptime(draw_date, _DRAW_DATE_FORMAT).date()


def _replace_draw_results(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    conn.execute(
        "delete from draw_results where jurisdiction_code = ? and game_slug = ?",
        (jurisdiction_code, game_slug),
    )
    _insert_draw_results(conn, jurisdiction_code, game_slug, draws)


def _insert_draw_results(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    for draw in draws:
        prize_rows = draw.prizes or (PrizeRow(0.0, 0, 0.0),)
        for prize in prize_rows:
            conn.execute(
                """
                insert into draw_results (
                    jurisdiction_code,
                    game_slug,
                    draw_date,
                    winning_number,
                    prize_amount,
                    wa_winners,
                    total
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    jurisdiction_code,
                    game_slug,
                    draw.draw_date,
                    draw.winning_number,
                    prize.prize_amount,
                    prize.wa_winners,
                    prize.total,
                ),
            )


def _money_to_float(value: str) -> float:
    return float(re.sub(r"[^0-9.]", "", value) or 0)


def _int_from_text(value: str) -> int:
    return int(re.sub(r"[^0-9]", "", value) or 0)
