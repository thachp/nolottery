from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict
from datetime import UTC, date, datetime

from .fetch_models import ParsedDraw, PrizeRow


def insert_snapshot(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    source_url: str,
    raw_content: str,
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
        (jurisdiction_code, game_slug, source_url, fetched_at, raw_content, parsed_json),
    )


def dedupe_draws(draws: tuple[ParsedDraw, ...]) -> tuple[ParsedDraw, ...]:
    deduped: dict[tuple[str, str], ParsedDraw] = {}
    for draw in draws:
        deduped[(draw.draw_date, draw.winning_number)] = draw
    return tuple(deduped.values())


def filter_newer_draws(
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


def replace_draw_results(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    draws: tuple[ParsedDraw, ...],
) -> None:
    conn.execute(
        "delete from draw_results where jurisdiction_code = ? and game_slug = ?",
        (jurisdiction_code, game_slug),
    )
    insert_draw_results(conn, jurisdiction_code, game_slug, draws)


def insert_draw_results(
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


def _parse_stored_draw_date(draw_date: str) -> date:
    for session in (" Evening", " Midday"):
        if draw_date.endswith(session):
            draw_date = draw_date[: -len(session)]
            break
    if match := re.match(
        r"^([A-Z][a-z]{2}, [A-Z][a-z]{2} \d{2}, \d{4}) ",
        draw_date,
    ):
        draw_date = match.group(1)
    return datetime.strptime(draw_date, "%a, %b %d, %Y").date()
