from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urlencode

from bs4 import BeautifulSoup, Tag

from nolottery.fetch_models import ParsedDraw
from nolottery.metadata import GameMetadata
from nolottery.result_adapters.common import (
    AdapterFetch,
    SourceReader,
    SourceSnapshot,
    _DRAW_DATE_FORMAT,
)

_DC_PAST_DRAW_NUMBERS_URL = "https://dclottery.com/winning-numbers/past-draw-numbers"
_DC_BACKFILL_START_DATE = "1982-08-24"
_DC_PAST_DRAW_NUMBERS_GAME_IDS = {
    "dc-3": 10,
    "dc-4": 11,
    "dc-5": 12,
    "powerball": 2,
    "mega-millions": 4,
    "lotto-america": 363,
    "millionaire-for-life": 376,
    "dc-keno": 1,
    "race2riches": 7,
}
_DC_PAST_DRAW_NUMBERS_GAMES = frozenset(_DC_PAST_DRAW_NUMBERS_GAME_IDS)
_DC_SESSION_NAMES = {
    "1:50pm": "Day",
    "7:50pm": "Evening",
    "11:30pm": "Night",
}


def parse_dc_past_draw_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("table.views-table tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        draw_date = _dc_draw_date(cells[0], cells[1])
        winning_number = _dc_winning_number(cells[2])
        if draw_date is None or not winning_number:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=winning_number,
                prizes=(),
            )
        )
    return tuple(draws)


def fetch_dc_past_draw_numbers_result(
    game: GameMetadata,
    source_dir,
    read_source: SourceReader,
    *,
    backfill: bool = False,
) -> AdapterFetch:
    page = 0
    all_draws: list[ParsedDraw] = []
    snapshots: list[SourceSnapshot] = []
    while True:
        source_name = (
            f"{game.slug}-dc-backfill-{page + 1}"
            if backfill
            else f"{game.slug}-dc-current"
        )
        raw_html, source_url = read_source(
            _dc_past_draw_numbers_url(game.slug, page=page if backfill else None),
            source_dir,
            source_name,
        )
        draws = parse_dc_past_draw_numbers_page(raw_html, game.slug)
        all_draws.extend(draws)
        snapshots.append(SourceSnapshot(source_url, raw_html, draws))
        if not backfill or _next_page(raw_html) is None:
            break
        page += 1

    return AdapterFetch(
        source_url=snapshots[0].source_url,
        draws=tuple(all_draws),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def _dc_past_draw_numbers_url(game_slug: str, *, page: int | None = None) -> str:
    query: dict[str, object] = {"game": _DC_PAST_DRAW_NUMBERS_GAME_IDS[game_slug]}
    if page is None:
        query["drawing_date"] = "past_week"
    else:
        query.update(
            {
                "drawing_date": "custom_range",
                "date[min]": _DC_BACKFILL_START_DATE,
                "date[max]": date.today().isoformat(),
            }
        )
        if page:
            query["page"] = page
    return f"{_DC_PAST_DRAW_NUMBERS_URL}?{urlencode(query)}"


def _dc_draw_date(date_cell: Tag, draw_cell: Tag) -> str | None:
    time_tag = date_cell.find("time")
    raw_date = (
        time_tag.get("datetime")
        if isinstance(time_tag, Tag) and time_tag.get("datetime")
        else date_cell.get_text(" ", strip=True)
    )
    if not isinstance(raw_date, str) or not raw_date.strip():
        return None
    try:
        parsed_date = datetime.fromisoformat(raw_date[:10])
    except ValueError:
        try:
            parsed_date = datetime.strptime(raw_date.strip(), "%b %d, %Y")
        except ValueError:
            return None

    draw_label = _compact_space(draw_cell.get_text(" ", strip=True))
    base_date = parsed_date.strftime(_DRAW_DATE_FORMAT)
    session = _DC_SESSION_NAMES.get(draw_label.lower())
    if session is not None:
        return f"{base_date} {session}"
    if draw_label:
        return f"{base_date} Draw {draw_label}"
    return base_date


def _dc_winning_number(number_cell: Tag) -> str:
    race_columns = number_cell.select(".race-2-riches-table-column")
    if race_columns:
        parts = []
        for column in race_columns:
            header = column.select_one(".race-2-riches-table-header")
            value = column.select_one(".race-2-riches-table-row")
            if header is not None and value is not None:
                header_text = header.get_text(" ", strip=True)
                value_text = value.get_text(" ", strip=True)
                parts.append(
                    f"{header_text} {value_text}"
                )
        return ", ".join(parts)

    ball_parts = [_dc_ball_text(ball) for ball in number_cell.select(".ball")]
    ball_parts = [part for part in ball_parts if part]
    all_star_bonus = number_cell.select_one(".allstarbonus")
    if all_star_bonus is not None:
        ball_parts.append(_compact_space(all_star_bonus.get_text(" ", strip=True)))
    return " ".join(ball_parts)


def _dc_ball_text(ball: Tag) -> str:
    value = _compact_space(ball.get_text(" ", strip=True))
    classes = set(ball.get("class", ()))
    if "powerball" in classes:
        return f"{value} Powerball"
    if "powerplay" in classes:
        return f"{value} Power Play"
    if "megaball" in classes:
        return f"{value} Mega Ball"
    if "starball" in classes:
        return f"{value} Star Ball"
    if "millionaireball" in classes:
        return f"{value} Millionaire Ball"
    if "highlight" in classes:
        return f"{value} Bonus"
    return value


def _next_page(raw_html: str) -> int | None:
    soup = BeautifulSoup(raw_html, "html.parser")
    link = soup.select_one(".pager-show-more a[href]")
    if link is None:
        return None
    match = re.search(r"[?&]page=(\d+)", str(link.get("href")))
    return int(match.group(1)) if match else None


def _compact_space(value: str) -> str:
    return " ".join(value.split())
