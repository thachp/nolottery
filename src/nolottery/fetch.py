from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .db import DEFAULT_JURISDICTION_CODE
from .fetch_models import FetchResult, ParsedDraw, PrizeRow
from .fetch_storage import (
    dedupe_draws,
    filter_newer_draws,
    insert_draw_results,
    insert_snapshot,
    replace_draw_results,
)
from .metadata import GameMetadata
from .result_adapters import (
    fetch_backfill_result,
    fetch_california_backfill_result,
    fetch_current_result,
    parse_available_years,
    parse_draws,
    year_url,
)
from .result_adapters.common import AdapterFetch, SourceSnapshot
from .result_adapters.arizona import parse_arizona_past_180_text
from .result_adapters.arkansas import parse_arkansas_did_i_win
from .result_adapters.california import (
    parse_california_daily3,
    parse_california_draw_game,
    parse_california_hot_spot,
    parse_california_hot_spot_backfill_json,
    parse_california_past_results_json,
)
from .result_adapters.colorado import parse_colorado_drawing_history
from .result_adapters.connecticut import parse_connecticut_winning_numbers
from .result_adapters.delaware import parse_delaware_search_winners
from .result_adapters.florida import parse_florida_pick_history_text
from .result_adapters.georgia import parse_georgia_draw_games_json
from .result_adapters.idaho import _idaho_history_url, parse_idaho_draw_page
from .result_adapters.illinois import parse_illinois_results_page
from .result_adapters.indiana import parse_indiana_draw_page
from .result_adapters.iowa import parse_iowa_winning_numbers_page
from .result_adapters.kentucky import parse_kentucky_winning_numbers_json
from .result_adapters.louisiana import parse_louisiana_latest_draw_page
from .result_adapters.maine import parse_maine_home_page
from .result_adapters.maryland import parse_maryland_winning_numbers_page
from .result_adapters.massachusetts import parse_massachusetts_draw_results_json
from .result_adapters.michigan import parse_michigan_draw_history_json
from .result_adapters.minnesota import parse_minnesota_winning_numbers_page
from .result_adapters.mississippi import parse_mississippi_home_page
from .result_adapters.missouri import parse_missouri_winning_numbers_page
from .result_adapters.montana import parse_montana_winning_numbers_table
from .result_adapters.national import parse_official_national_results_page
from .result_adapters.nebraska import parse_nebraska_draw_results_page
from .result_adapters.new_york import parse_new_york_daily_numbers_json
from .result_adapters.texas import parse_texas_winning_numbers
from .result_adapters.washington import parse_past_drawings

_dedupe_draws = dedupe_draws
_filter_newer_draws = filter_newer_draws
_insert_draw_results = insert_draw_results
_insert_snapshot = insert_snapshot
_parse_draws = parse_draws
_replace_draw_results = replace_draw_results
_year_url = year_url


def fetch_game(
    conn: sqlite3.Connection,
    game: GameMetadata,
    source_file: Path | None = None,
    jurisdiction_code: str = DEFAULT_JURISDICTION_CODE,
) -> FetchResult:
    if source_file is not None:
        raw_content = source_file.read_text(encoding="utf-8")
        source_url = source_file.as_uri()
        draws = parse_draws(raw_content, jurisdiction_code, game.slug)
        result = _single_snapshot_result(source_url, raw_content, draws)
    else:
        result = fetch_current_result(
            jurisdiction_code,
            game,
            source_dir=None,
            read_source=_read_source,
        )
        if result is None:
            raw_content, source_url = _read_source(game.source_url, None, game.slug)
            draws = parse_draws(raw_content, jurisdiction_code, game.slug)
            result = _single_snapshot_result(source_url, raw_content, draws)

    new_draws = _persist_incremental_fetch(
        conn,
        jurisdiction_code,
        game.slug,
        result,
    )
    conn.commit()
    return _fetch_result(game, result.source_url, new_draws)


def fetch_game_backfill(
    conn: sqlite3.Connection,
    game: GameMetadata,
    source_dir: Path | None = None,
    jurisdiction_code: str = DEFAULT_JURISDICTION_CODE,
) -> FetchResult:
    result = fetch_backfill_result(
        jurisdiction_code,
        game,
        source_dir,
        read_source=_read_source,
    )
    if result is None:
        discovery_html, discovery_url = _read_source(
            game.source_url,
            source_dir,
            game.slug,
        )
        if jurisdiction_code == "ca":
            result = fetch_california_backfill_result(
                game,
                discovery_html,
                discovery_url,
                source_dir,
                read_source=_read_source,
            )
        else:
            result = _fetch_yearly_backfill(
                game,
                discovery_html,
                discovery_url,
                source_dir,
                jurisdiction_code,
            )

    _persist_backfill(conn, jurisdiction_code, game.slug, result)
    conn.commit()
    return _fetch_result(game, result.source_url, result.draws, result.page_count)


def _fetch_yearly_backfill(
    game: GameMetadata,
    discovery_html: str,
    discovery_url: str,
    source_dir: Path | None,
    jurisdiction_code: str,
) -> AdapterFetch:
    years = parse_available_years(discovery_html)
    if not years:
        years = (datetime.now(tz=UTC).year,)

    all_draws: list[ParsedDraw] = []
    snapshots: list[SourceSnapshot] = []
    for year in years:
        raw_content, source_url = _read_source(
            year_url(game.source_url, year),
            source_dir,
            f"{game.slug}-{year}",
        )
        draws = parse_draws(raw_content, jurisdiction_code, game.slug)
        all_draws.extend(draws)
        snapshots.append(SourceSnapshot(source_url, raw_content, draws))

    return AdapterFetch(
        source_url=discovery_url,
        draws=dedupe_draws(tuple(all_draws)),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def _persist_incremental_fetch(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    result: AdapterFetch,
) -> tuple[ParsedDraw, ...]:
    for snapshot in result.snapshots:
        insert_snapshot(
            conn,
            jurisdiction_code,
            game_slug,
            snapshot.source_url,
            snapshot.raw_content,
            snapshot.draws,
        )
    new_draws = filter_newer_draws(conn, jurisdiction_code, game_slug, result.draws)
    insert_draw_results(conn, jurisdiction_code, game_slug, new_draws)
    return new_draws


def _persist_backfill(
    conn: sqlite3.Connection,
    jurisdiction_code: str,
    game_slug: str,
    result: AdapterFetch,
) -> None:
    for snapshot in result.snapshots:
        insert_snapshot(
            conn,
            jurisdiction_code,
            game_slug,
            snapshot.source_url,
            snapshot.raw_content,
            snapshot.draws,
        )
    replace_draw_results(conn, jurisdiction_code, game_slug, result.draws)


def _fetch_result(
    game: GameMetadata,
    source_url: str,
    draws: tuple[ParsedDraw, ...],
    page_count: int = 1,
) -> FetchResult:
    return FetchResult(
        game_name=game.name,
        source_url=source_url,
        draw_count=len(draws),
        prize_row_count=sum(len(draw.prizes) for draw in draws),
        page_count=page_count,
    )


def _single_snapshot_result(
    source_url: str,
    raw_content: str,
    draws: tuple[ParsedDraw, ...],
) -> AdapterFetch:
    return AdapterFetch(
        source_url=source_url,
        draws=draws,
        snapshots=(SourceSnapshot(source_url, raw_content, draws),),
        page_count=1,
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
