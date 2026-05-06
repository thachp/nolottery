from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup, Tag

from .metadata import GameMetadata

_DRAW_DATE_FORMAT = "%a, %b %d, %Y"


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
) -> FetchResult:
    if source_file is not None:
        raw_html = source_file.read_text(encoding="utf-8")
        source_url = source_file.as_uri()
    else:
        raw_html, source_url = _read_source(game.source_url, None, game.slug)

    draws = parse_past_drawings(raw_html)
    _insert_snapshot(conn, game.slug, source_url, raw_html, draws)
    new_draws = _filter_newer_draws(conn, game.slug, draws)
    _insert_draw_results(conn, game.slug, new_draws)
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
) -> FetchResult:
    discovery_html, discovery_url = _read_source(game.source_url, source_dir, game.slug)
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
        draws = parse_past_drawings(raw_html)
        all_draws.extend(draws)
        _insert_snapshot(conn, game.slug, source_url, raw_html, draws)
        page_count += 1

    deduped_draws = _dedupe_draws(tuple(all_draws))
    _replace_draw_results(conn, game.slug, deduped_draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=discovery_url,
        draw_count=len(deduped_draws),
        prize_row_count=sum(len(draw.prizes) for draw in deduped_draws),
        page_count=page_count,
    )


def parse_past_drawings(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.table-viewport-large"):
        draw = _parse_large_table(table)
        if draw is not None:
            draws.append(draw)
    return tuple(draws)


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
) -> tuple[str, str]:
    if source_dir is None:
        response = httpx.get(source_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        return response.text, str(response.url)

    source_file = source_dir / f"{source_name}.html"
    return source_file.read_text(encoding="utf-8"), source_file.as_uri()


def _year_url(source_url: str, year: int) -> str:
    parsed = urlparse(source_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["unitcount"] = str(year)
    query["unittype"] = "year"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _insert_snapshot(
    conn: sqlite3.Connection,
    game_slug: str,
    source_url: str,
    raw_html: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    parsed_json = json.dumps([asdict(draw) for draw in draws], sort_keys=True)
    fetched_at = datetime.now(tz=UTC).isoformat()
    conn.execute(
        """
        insert into fetch_snapshots (game_slug, source_url, fetched_at, raw_html, parsed_json)
        values (?, ?, ?, ?, ?)
        """,
        (game_slug, source_url, fetched_at, raw_html, parsed_json),
    )


def _dedupe_draws(draws: tuple[ParsedDraw, ...]) -> tuple[ParsedDraw, ...]:
    deduped: dict[tuple[str, str], ParsedDraw] = {}
    for draw in draws:
        deduped[(draw.draw_date, draw.winning_number)] = draw
    return tuple(deduped.values())


def _filter_newer_draws(
    conn: sqlite3.Connection,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> tuple[ParsedDraw, ...]:
    latest_draw_date = _latest_stored_draw_date(conn, game_slug)
    existing_keys = _existing_draw_keys(conn, game_slug)

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


def _latest_stored_draw_date(conn: sqlite3.Connection, game_slug: str) -> date | None:
    rows = conn.execute(
        """
        select distinct draw_date
        from draw_results
        where game_slug = ?
        """,
        (game_slug,),
    ).fetchall()
    parsed_dates = [
        parsed_date
        for row in rows
        if (parsed_date := _parse_draw_date(row["draw_date"])) is not None
    ]
    return max(parsed_dates, default=None)


def _existing_draw_keys(
    conn: sqlite3.Connection,
    game_slug: str,
) -> set[tuple[str, str]]:
    rows = conn.execute(
        """
        select distinct draw_date, winning_number
        from draw_results
        where game_slug = ?
        """,
        (game_slug,),
    ).fetchall()
    return {(row["draw_date"], row["winning_number"]) for row in rows}


def _parse_draw_date(draw_date: str) -> date | None:
    try:
        return datetime.strptime(draw_date, _DRAW_DATE_FORMAT).date()
    except ValueError:
        return None


def _replace_draw_results(
    conn: sqlite3.Connection,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    conn.execute("delete from draw_results where game_slug = ?", (game_slug,))
    _insert_draw_results(conn, game_slug, draws)


def _insert_draw_results(
    conn: sqlite3.Connection,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    for draw in draws:
        prize_rows = draw.prizes or (PrizeRow(0.0, 0, 0.0),)
        for prize in prize_rows:
            conn.execute(
                """
                insert into draw_results (
                    game_slug,
                    draw_date,
                    winning_number,
                    prize_amount,
                    wa_winners,
                    total
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                (
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
