from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

from nolottery.fetch_models import ParsedDraw
from nolottery.metadata import GameMetadata
from nolottery.result_adapters.common import (
    AdapterFetch,
    SourceReader,
    SourceSnapshot,
    _DRAW_DATE_FORMAT,
)

_NEBRASKA_SEARCH_NUMBERS_URL = "https://nelottery.com/homeapp/lotto/searchnumbers"
_NEBRASKA_BACKFILL_START_DATE = "01/01/1985"
_NEBRASKA_DRAW_RESULTS_GAMES = {
    "powerball": (28, "Powerball", ("", "Powerball", None)),
    "mega-millions": (30, "Mega Millions", ("", "Mega Ball")),
    "lotto-america": (40, "Lotto America", ("", "Star Ball", None)),
    "millionaire-for-life": (42, "Millionaire for Life", ("", "Millionaire Ball")),
    "lucky-for-life": (37, "Lucky for Life", ("", "Lucky Ball")),
    "nebraska-pick-5": (31, "Pick 5", ("",)),
    "nebraska-pick-4": (41, "Pick 4", ("",)),
    "nebraska-pick-3": (32, "Pick 3", ("",)),
    "nebraska-myday": (33, "MyDaY", ("Month", "Day", "Year")),
    "nebraska-2by2": (34, "2by2", ("Red", "White")),
}


def fetch_nebraska_result(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
    *,
    backfill: bool = False,
) -> AdapterFetch:
    if backfill:
        source_name = f"{game.slug}-ne-backfill"
        if source_dir is not None:
            raw_html, source_url = read_source(
                _NEBRASKA_SEARCH_NUMBERS_URL,
                source_dir,
                source_name,
            )
        else:
            raw_html, source_url = _read_nebraska_search_numbers(game.slug)
    else:
        raw_html, source_url = read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-ne-current",
        )

    draws = parse_nebraska_draw_results_page(raw_html, game.slug)
    return AdapterFetch(
        source_url=source_url,
        draws=draws,
        snapshots=(SourceSnapshot(source_url, raw_html, draws),),
        page_count=1,
    )


def parse_nebraska_draw_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, game_name, number_labels = _NEBRASKA_DRAW_RESULTS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    heading = next(
        (
            heading
            for heading in soup.select("h2, h3")
            if heading.get_text(" ", strip=True) == f"{game_name} Numbers"
        ),
        None,
    )
    if heading is None:
        return ()
    table = heading.find_next("table", class_="numbertable")
    if table is None:
        return ()

    draws: list[ParsedDraw] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        draw_date = _nebraska_draw_date(cells[0].get_text(" ", strip=True))
        winning_number = _nebraska_winning_number(cells[1:], number_labels)
        if draw_date is None or winning_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
    return tuple(draws)


def _read_nebraska_search_numbers(game_slug: str) -> tuple[str, str]:
    game_id, _, _ = _NEBRASKA_DRAW_RESULTS_GAMES[game_slug]
    response = httpx.post(
        _NEBRASKA_SEARCH_NUMBERS_URL,
        data={
            "game_id": str(game_id),
            "date_start": _NEBRASKA_BACKFILL_START_DATE,
            "date_end": datetime.now(tz=UTC).strftime("%m/%d/%Y"),
            "submit": "Submit",
        },
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)


def _nebraska_winning_number(
    number_cells: list[Tag],
    number_labels: tuple[str | None, ...],
) -> str | None:
    parts: list[str] = []
    for cell, label in zip(number_cells, number_labels, strict=False):
        if label is None:
            continue
        for raw_number in cell.get_text(" ", strip=True).split(","):
            number = _nebraska_number(raw_number)
            if number is None:
                continue
            parts.append(f"{number} {label}" if label else number)
    return ", ".join(parts) if parts else None


def _nebraska_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None

def _nebraska_number(raw_value: str) -> str | None:
    value = raw_value.strip()
    if re.fullmatch(r"\d{1,2}", value) is None:
        return None
    return str(int(value))
