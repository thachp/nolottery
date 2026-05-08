from __future__ import annotations

import json
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from math import ceil
from pathlib import Path
from urllib.parse import urlencode, urljoin

from nolottery.fetch_models import ParsedDraw
from nolottery.fetch_storage import dedupe_draws
from nolottery.metadata import GameMetadata
from nolottery.result_adapters import (
    arizona,
    arkansas,
    california,
    colorado,
    connecticut,
    delaware,
    florida,
    georgia,
    idaho,
    illinois,
    indiana,
    iowa,
    kentucky,
    louisiana,
    maine,
    maryland,
    massachusetts,
    michigan,
    minnesota,
    mississippi,
    missouri,
    montana,
    national,
    nebraska,
    new_york,
    oregon,
    texas,
    washington,
)
from nolottery.result_adapters.common import AdapterFetch, SourceReader, SourceSnapshot

Parser = Callable[[str, str], tuple[ParsedDraw, ...]]


def fetch_current_result(
    jurisdiction_code: str,
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch | None:
    if jurisdiction_code == "fl" and game.slug in florida._FLORIDA_PICK_GAMES:
        return _florida_fetch(game, source_dir)
    if jurisdiction_code == "ny" and game.slug in new_york._NEW_YORK_DAILY_GAMES:
        return _new_york_fetch(game, source_dir, read_source)
    if jurisdiction_code == "az" and game.slug in arizona._ARIZONA_PAST_180_GAMES:
        return _arizona_fetch(game, source_dir)
    if jurisdiction_code == "ct" and game.slug in connecticut._CONNECTICUT_WINNING_NUMBERS_GAMES:
        return _source_function_fetch(
            game,
            source_dir,
            connecticut._connecticut_winning_numbers_draws_source,
            connecticut.parse_connecticut_winning_numbers,
        )
    if jurisdiction_code == "de" and game.slug in delaware._DELAWARE_SEARCH_WINNERS_GAMES:
        return _delaware_fetch(game, source_dir, read_source)
    if jurisdiction_code == "ga" and game.slug in georgia._GEORGIA_DRAW_GAMES:
        return _georgia_fetch(game, source_dir, read_source)
    if jurisdiction_code == "ky" and game.slug in kentucky._KENTUCKY_WINNING_NUMBERS_GAMES:
        return _source_function_fetch(
            game,
            source_dir,
            kentucky._kentucky_winning_numbers_source,
            kentucky.parse_kentucky_winning_numbers_json,
        )
    if jurisdiction_code == "ma" and game.slug in massachusetts._MASSACHUSETTS_DRAW_RESULTS_GAMES:
        return _massachusetts_fetch(game, source_dir, read_source)
    if jurisdiction_code == "mi" and game.slug in michigan._MICHIGAN_DRAW_HISTORY_GAMES:
        return _source_function_fetch(
            game,
            source_dir,
            michigan._michigan_draw_history_source,
            michigan.parse_michigan_draw_history_json,
        )
    if jurisdiction_code == "or" and game.slug in oregon._OREGON_API_GAMES:
        return oregon.fetch_oregon_result(game, source_dir, read_source)

    simple_specs = _current_simple_specs()
    spec = simple_specs.get(jurisdiction_code)
    if spec is None or game.slug not in spec.game_slugs:
        return None
    return _read_and_parse(
        read_source,
        game.source_url,
        source_dir,
        f"{game.slug}-{jurisdiction_code}-backfill",
        game.slug,
        spec.parser,
    )


def fetch_backfill_result(
    jurisdiction_code: str,
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch | None:
    if (
        jurisdiction_code in national._OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS
        and game.slug in national._OFFICIAL_NATIONAL_RESULTS_GAMES
    ):
        return _read_and_parse(
            read_source,
            game.source_url,
            source_dir,
            game.slug,
            game.slug,
            national.parse_official_national_results_page,
        )
    if jurisdiction_code == "ca":
        return None
    if jurisdiction_code == "tx" and game.slug in texas._TEXAS_WINNING_NUMBER_GAMES:
        return _read_and_parse(
            read_source,
            game.source_url,
            source_dir,
            game.slug,
            game.slug,
            texas.parse_texas_winning_numbers,
        )
    if jurisdiction_code == "id" and game.slug in idaho._IDAHO_DRAW_PAGE_GAMES:
        return _read_and_parse(
            read_source,
            idaho._idaho_history_url(game),
            source_dir,
            f"{game.slug}-id-backfill",
            game.slug,
            idaho.parse_idaho_draw_page,
        )
    if jurisdiction_code == "co" and game.slug in colorado._COLORADO_DRAWING_HISTORY_GAMES:
        return colorado.fetch_colorado_backfill_result(game, source_dir, read_source)
    if jurisdiction_code == "or" and game.slug in oregon._OREGON_API_GAMES:
        return oregon.fetch_oregon_result(game, source_dir, read_source)
    return fetch_current_result(jurisdiction_code, game, source_dir, read_source)


def fetch_california_backfill_result(
    game: GameMetadata,
    discovery_html: str,
    discovery_url: str,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    if game.slug == "hot-spot":
        return _fetch_california_hot_spot_backfill(
            game,
            discovery_url,
            source_dir,
            read_source,
        )

    api_path, game_id, configured_total = california._parse_california_past_results_config(
        discovery_html,
        game.slug,
    )
    all_draws: list[ParsedDraw] = []
    snapshots: list[SourceSnapshot] = []
    page = 1
    total_results = configured_total

    while True:
        api_url = urljoin(
            game.source_url,
            f"{api_path}{game_id}/{page}/{california._CALIFORNIA_BACKFILL_PAGE_SIZE}",
        )
        raw_json, source_url = read_source(
            api_url,
            source_dir,
            f"{game.slug}-ca-backfill-{page}",
            suffix=".json",
        )
        payload = json.loads(raw_json)
        if payload is None:
            draws = ()
            snapshots.append(SourceSnapshot(source_url, raw_json, draws))
            break

        total_results = int(payload.get("TotalPreviousDraws") or total_results or 0)
        draws = california.parse_california_past_results_json(raw_json, game.slug)
        all_draws.extend(draws)
        snapshots.append(SourceSnapshot(source_url, raw_json, draws))

        total_pages = ceil(total_results / california._CALIFORNIA_BACKFILL_PAGE_SIZE)
        if page >= total_pages or len(draws) < california._CALIFORNIA_BACKFILL_PAGE_SIZE:
            break
        page += 1

    return AdapterFetch(
        source_url=discovery_url,
        draws=dedupe_draws(tuple(all_draws)),
        snapshots=tuple(snapshots),
        page_count=len(snapshots),
    )


def parse_draws(
    raw_content: str,
    jurisdiction_code: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    if (
        jurisdiction_code in national._OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS
        and game_slug in national._OFFICIAL_NATIONAL_RESULTS_GAMES
    ):
        return national.parse_official_national_results_page(raw_content, game_slug)
    if jurisdiction_code == "ca" and game_slug == "hot-spot":
        return california.parse_california_hot_spot(raw_content)
    if jurisdiction_code == "ca" and game_slug in california._CALIFORNIA_GAME_SLUGS:
        return california.parse_california_draw_game(raw_content)
    if jurisdiction_code == "or" and game_slug in oregon._OREGON_API_GAMES:
        return oregon.parse_oregon_api_results_json(raw_content, game_slug)

    spec = _parse_specs().get(jurisdiction_code)
    if spec is not None and game_slug in spec.game_slugs:
        return spec.parser(raw_content, game_slug)
    return washington.parse_past_drawings(raw_content)


def parse_available_years(raw_html: str) -> tuple[int, ...]:
    return washington.parse_available_years(raw_html)


def year_url(source_url: str, year: int) -> str:
    return washington._year_url(source_url, year)


class _ParseSpec:
    def __init__(self, game_slugs: Collection[str], parser: Parser) -> None:
        self.game_slugs = game_slugs
        self.parser = parser


def _current_simple_specs() -> dict[str, _ParseSpec]:
    return {
        "ar": _ParseSpec(arkansas._ARKANSAS_DID_I_WIN_GAMES, arkansas.parse_arkansas_did_i_win),
        "co": _ParseSpec(colorado._COLORADO_DRAWING_HISTORY_GAMES, colorado.parse_colorado_drawing_history),
        "id": _ParseSpec(idaho._IDAHO_DRAW_PAGE_GAMES, idaho.parse_idaho_draw_page),
        "il": _ParseSpec(illinois._ILLINOIS_RESULTS_PAGE_GAMES, illinois.parse_illinois_results_page),
        "in": _ParseSpec(indiana._INDIANA_DRAW_PAGE_GAMES, indiana.parse_indiana_draw_page),
        "ia": _ParseSpec(iowa._IOWA_WINNING_NUMBERS_GAMES, iowa.parse_iowa_winning_numbers_page),
        "la": _ParseSpec(louisiana._LOUISIANA_LATEST_DRAW_GAMES, louisiana.parse_louisiana_latest_draw_page),
        "me": _ParseSpec(maine._MAINE_HOME_PAGE_GAMES, maine.parse_maine_home_page),
        "md": _ParseSpec(maryland._MARYLAND_WINNING_NUMBERS_GAMES, maryland.parse_maryland_winning_numbers_page),
        "mn": _ParseSpec(minnesota._MINNESOTA_WINNING_NUMBERS_GAMES, minnesota.parse_minnesota_winning_numbers_page),
        "ms": _ParseSpec(mississippi._MISSISSIPPI_HOME_PAGE_GAMES, mississippi.parse_mississippi_home_page),
        "mo": _ParseSpec(missouri._MISSOURI_WINNING_NUMBERS_GAMES, missouri.parse_missouri_winning_numbers_page),
        "mt": _ParseSpec(montana._MONTANA_WINNING_NUMBERS_GAMES, montana.parse_montana_winning_numbers_table),
        "ne": _ParseSpec(nebraska._NEBRASKA_DRAW_RESULTS_GAMES, nebraska.parse_nebraska_draw_results_page),
    }


def _parse_specs() -> dict[str, _ParseSpec]:
    specs = _current_simple_specs()
    specs.update(
        {
            "az": _ParseSpec(arizona._ARIZONA_PAST_180_GAMES, arizona.parse_arizona_past_180_text),
            "ct": _ParseSpec(connecticut._CONNECTICUT_WINNING_NUMBERS_GAMES, connecticut.parse_connecticut_winning_numbers),
            "de": _ParseSpec(delaware._DELAWARE_SEARCH_WINNERS_GAMES, delaware.parse_delaware_search_winners),
            "fl": _ParseSpec(florida._FLORIDA_PICK_GAMES, florida.parse_florida_pick_history_text),
            "ga": _ParseSpec(georgia._GEORGIA_DRAW_GAMES, georgia.parse_georgia_draw_games_json),
            "ky": _ParseSpec(kentucky._KENTUCKY_WINNING_NUMBERS_GAMES, kentucky.parse_kentucky_winning_numbers_json),
            "ma": _ParseSpec(massachusetts._MASSACHUSETTS_DRAW_RESULTS_GAMES, massachusetts.parse_massachusetts_draw_results_json),
            "mi": _ParseSpec(michigan._MICHIGAN_DRAW_HISTORY_GAMES, michigan.parse_michigan_draw_history_json),
            "ny": _ParseSpec(new_york._NEW_YORK_DAILY_GAMES, new_york.parse_new_york_daily_numbers_json),
            "or": _ParseSpec(oregon._OREGON_API_GAMES, oregon.parse_oregon_api_results_json),
            "tx": _ParseSpec(texas._TEXAS_WINNING_NUMBER_GAMES, texas.parse_texas_winning_numbers),
        }
    )
    return specs


def _read_and_parse(
    read_source: SourceReader,
    source_url: str,
    source_dir: Path | None,
    source_name: str,
    game_slug: str,
    parser: Parser,
    *,
    suffix: str = ".html",
) -> AdapterFetch:
    raw_content, resolved_url = read_source(
        source_url,
        source_dir,
        source_name,
        suffix=suffix,
    )
    draws = parser(raw_content, game_slug)
    return _single_snapshot_result(resolved_url, raw_content, draws)


def _source_function_fetch(
    game: GameMetadata,
    source_dir: Path | None,
    source: Callable[[GameMetadata, Path | None], tuple[str, str]],
    parser: Parser,
) -> AdapterFetch:
    raw_content, source_url = source(game, source_dir)
    draws = parser(raw_content, game.slug)
    return _single_snapshot_result(source_url, raw_content, draws)


def _florida_fetch(game: GameMetadata, source_dir: Path | None) -> AdapterFetch:
    raw_text, source_url, draws = florida._florida_pick_history_draws(
        game.slug,
        source_dir=source_dir,
    )
    return _single_snapshot_result(source_url, raw_text, draws)


def _new_york_fetch(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    return _read_and_parse(
        read_source,
        new_york._NEW_YORK_DAILY_NUMBERS_URL,
        source_dir,
        f"{game.slug}-ny-backfill",
        game.slug,
        new_york.parse_new_york_daily_numbers_json,
        suffix=".json",
    )


def _arizona_fetch(game: GameMetadata, source_dir: Path | None) -> AdapterFetch:
    raw_text, source_url, draws = arizona._arizona_past_180_draws(
        game,
        source_dir=source_dir,
    )
    return _single_snapshot_result(source_url, raw_text, draws)


def _delaware_fetch(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    source_name = f"{game.slug}-de-backfill"
    if source_dir is not None:
        source_url = (source_dir / f"{source_name}.html").as_uri()
        raw_html = (source_dir / f"{source_name}.html").read_text(encoding="utf-8")
    else:
        game_path, _, _ = delaware._DELAWARE_SEARCH_WINNERS_GAMES[game.slug]
        today = datetime.now(tz=UTC).date()
        url = (
            "https://www.delottery.com/Winning-Numbers/Search-Winners/"
            f"{today.year}/{today.month}/{game_path}"
        )
        raw_html, source_url = read_source(url, None, source_name)
    draws = delaware.parse_delaware_search_winners(raw_html, game.slug)
    return _single_snapshot_result(source_url, raw_html, draws)


def _georgia_fetch(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    source_name = f"{game.slug}-ga-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        raw_json, source_url = source_file.read_text(encoding="utf-8"), source_file.as_uri()
    else:
        game_name, _, _ = georgia._GEORGIA_DRAW_GAMES[game.slug]
        query = urlencode(
            {
                "game-names": game_name,
                "previous-draws": "180",
                "page": "0",
                "size": "180",
            }
        )
        url = f"https://www.galottery.com/api/v2/draw-games/draws/page?{query}"
        raw_json, source_url = read_source(url, None, source_name, suffix=".json")
    draws = georgia.parse_georgia_draw_games_json(raw_json, game.slug)
    return _single_snapshot_result(source_url, raw_json, draws)


def _massachusetts_fetch(
    game: GameMetadata,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    source_name = f"{game.slug}-ma-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        raw_json, source_url = source_file.read_text(encoding="utf-8"), source_file.as_uri()
    else:
        raw_json, source_url = read_source(
            "https://www.masslottery.com/api/v1/draw-results",
            None,
            source_name,
            suffix=".json",
        )
    draws = massachusetts.parse_massachusetts_draw_results_json(raw_json, game.slug)
    return _single_snapshot_result(source_url, raw_json, draws)


def _fetch_california_hot_spot_backfill(
    game: GameMetadata,
    discovery_url: str,
    source_dir: Path | None,
    read_source: SourceReader,
) -> AdapterFetch:
    source_url = "https://www.calottery.com/api/v1.5/drawgames/22"
    api_url = f"{source_url}?drawscount={california._CALIFORNIA_HOT_SPOT_BACKFILL_COUNT}"
    raw_json, resolved_url = read_source(
        api_url,
        source_dir,
        f"{game.slug}-ca-backfill-1",
        suffix=".json",
    )
    draws = california.parse_california_hot_spot_backfill_json(raw_json)
    return AdapterFetch(
        source_url=discovery_url,
        draws=draws,
        snapshots=(SourceSnapshot(resolved_url, raw_json, draws),),
        page_count=1,
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
