from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

from .metadata import GameMetadata


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


def fetch_game(
    conn: sqlite3.Connection,
    game: GameMetadata,
    source_file: Path | None = None,
) -> FetchResult:
    if source_file is None:
        response = httpx.get(game.source_url, follow_redirects=True, timeout=30)
        response.raise_for_status()
        raw_html = response.text
        source_url = str(response.url)
    else:
        raw_html = source_file.read_text(encoding="utf-8")
        source_url = source_file.as_uri()

    draws = parse_past_drawings(raw_html)
    parsed_json = json.dumps([asdict(draw) for draw in draws], sort_keys=True)
    fetched_at = datetime.now(tz=UTC).isoformat()
    conn.execute(
        """
        insert into fetch_snapshots (game_slug, source_url, fetched_at, raw_html, parsed_json)
        values (?, ?, ?, ?, ?)
        """,
        (game.slug, source_url, fetched_at, raw_html, parsed_json),
    )
    _replace_draw_results(conn, game.slug, draws)
    conn.commit()

    return FetchResult(
        game_name=game.name,
        source_url=source_url,
        draw_count=len(draws),
        prize_row_count=sum(len(draw.prizes) for draw in draws),
    )


def parse_past_drawings(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.table-viewport-large"):
        draw = _parse_large_table(table)
        if draw is not None:
            draws.append(draw)
    return tuple(draws)


def _parse_large_table(table: Tag) -> ParsedDraw | None:
    date_node = table.select_one("thead .h2-like")
    ball_nodes = table.select("td.game-balls li")
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


def _replace_draw_results(
    conn: sqlite3.Connection,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    conn.execute("delete from draw_results where game_slug = ?", (game_slug,))
    for draw in draws:
        for prize in draw.prizes:
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
