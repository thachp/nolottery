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
from zoneinfo import ZoneInfo

import httpx
import pdfplumber
from bs4 import BeautifulSoup, NavigableString, Tag

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
_ARKANSAS_DID_I_WIN_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_COLORADO_DRAWING_HISTORY_GAMES = {
    "mega-millions": ("Mega Millions Numbers", "Mega Ball"),
    "powerball": ("Powerball Numbers", "Powerball"),
}
_ARIZONA_PAST_180_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_TEXAS_SPECIAL_NUMBER_NAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_CONNECTICUT_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("11", "MegaMillions", "Mega Ball"),
    "powerball": ("5", "Powerball", "Powerball"),
}
_DELAWARE_SEARCH_WINNERS_GAMES = {
    "mega-millions": ("MEGA-MILLIONS", "Mega Millions", "Mega Ball"),
    "powerball": ("POWERBALL", "Powerball", "Powerball"),
}
_GEORGIA_DRAW_GAMES = {
    "mega-millions": ("MEGA MILLIONS", "MB", "Mega Ball"),
    "powerball": ("POWERBALL", "PB", "Powerball"),
}
_GEORGIA_TIMEZONE = ZoneInfo("America/New_York")
_IDAHO_DRAW_PAGE_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_ILLINOIS_RESULTS_PAGE_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_INDIANA_DRAW_PAGE_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_IOWA_WINNING_NUMBERS_GAMES = {
    "mega-millions": (1, "Mega Ball"),
    "powerball": (0, "Powerball"),
}
_KENTUCKY_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("26", "MEGABALL", "Mega Ball"),
    "powerball": ("12", "POWERBALL", "Powerball"),
}
_LOUISIANA_LATEST_DRAW_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_MAINE_HOME_PAGE_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}
_MARYLAND_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}
_MASSACHUSETTS_DRAW_RESULTS_GAMES = {
    "mega-millions": ("mega_millions", "megaball", "Mega Ball"),
    "powerball": ("powerball", "powerball", "Powerball"),
}
_MICHIGAN_DRAW_HISTORY_GAMES = {
    "mega-millions": ("B", "megaball", "Mega Ball"),
    "powerball": ("P", "powerball", "Powerball"),
}
_MINNESOTA_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}
_MISSISSIPPI_HOME_PAGE_GAMES = {
    "mega-millions": ("mega-millions", "Mega Ball"),
    "powerball": ("powerball", "Powerball"),
}
_MISSOURI_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("num_yellow", "Mega Ball"),
    "powerball": ("num_red", "Powerball"),
}
_MONTANA_WINNING_NUMBERS_GAMES = {
    "mega-millions": ("Mega Ball", {"Mega Ball"}),
    "powerball": ("Powerball", {"PB", "PP"}),
}
_NEBRASKA_DRAW_RESULTS_GAMES = {
    "mega-millions": ("Mega Millions", "Mega Ball"),
    "powerball": ("Powerball", "Powerball"),
}
_OFFICIAL_NATIONAL_RESULTS_GAMES = {
    "mega-millions": "Mega Ball",
    "powerball": "Powerball",
}
_OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS = {"dc", "ks"}
_NATIONAL_DRAW_DATE_RE = re.compile(
    r"^(Sun|Mon|Tue|Wed|Thu|Fri|Sat),\s+"
    r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})"
)
_MICHIGAN_DRAW_HISTORY_QUERY = """
query Game($gameCode: String!, $startDateString: String!, $endDateString: String!) {
  gameByCode(code: $gameCode) {
    logicalGameIdentifier
    drawResultsBetweenDates(
      startDateString: $startDateString,
      endDateString: $endDateString
    ) {
      drawDate
      drawSequence
      hasPayoutData
      isBonusDraw
      winningNumbers {
        drawNumbers
        powerball
        powerplay
        megaball
        megaplier
      }
    }
  }
}
"""


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
        and jurisdiction_code == "md"
        and game.slug in _MARYLAND_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-md-backfill",
        )
        draws = parse_maryland_winning_numbers_page(raw_html, game.slug)
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
        and jurisdiction_code == "ma"
        and game.slug in _MASSACHUSETTS_DRAW_RESULTS_GAMES
    ):
        raw_json, source_url = _massachusetts_draw_results_source(
            game,
            source_dir=None,
        )
        draws = parse_massachusetts_draw_results_json(raw_json, game.slug)
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
    if (
        source_file is None
        and jurisdiction_code == "mi"
        and game.slug in _MICHIGAN_DRAW_HISTORY_GAMES
    ):
        raw_json, source_url = _michigan_draw_history_source(game, source_dir=None)
        draws = parse_michigan_draw_history_json(raw_json, game.slug)
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
    if (
        source_file is None
        and jurisdiction_code == "mn"
        and game.slug in _MINNESOTA_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-mn-backfill",
        )
        draws = parse_minnesota_winning_numbers_page(raw_html, game.slug)
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
        and jurisdiction_code == "ms"
        and game.slug in _MISSISSIPPI_HOME_PAGE_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-ms-backfill",
        )
        draws = parse_mississippi_home_page(raw_html, game.slug)
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
        and jurisdiction_code == "mo"
        and game.slug in _MISSOURI_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-mo-backfill",
        )
        draws = parse_missouri_winning_numbers_page(raw_html, game.slug)
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
        and jurisdiction_code == "mt"
        and game.slug in _MONTANA_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-mt-backfill",
        )
        draws = parse_montana_winning_numbers_table(raw_html, game.slug)
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
        and jurisdiction_code == "ne"
        and game.slug in _NEBRASKA_DRAW_RESULTS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-ne-backfill",
        )
        draws = parse_nebraska_draw_results_page(raw_html, game.slug)
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
        and jurisdiction_code == "me"
        and game.slug in _MAINE_HOME_PAGE_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-me-backfill",
        )
        draws = parse_maine_home_page(raw_html, game.slug)
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
        and jurisdiction_code == "la"
        and game.slug in _LOUISIANA_LATEST_DRAW_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-la-backfill",
        )
        draws = parse_louisiana_latest_draw_page(raw_html, game.slug)
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
        and jurisdiction_code == "ky"
        and game.slug in _KENTUCKY_WINNING_NUMBERS_GAMES
    ):
        raw_json, source_url = _kentucky_winning_numbers_source(
            game,
            source_dir=None,
        )
        draws = parse_kentucky_winning_numbers_json(raw_json, game.slug)
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
    if (
        source_file is None
        and jurisdiction_code == "ia"
        and game.slug in _IOWA_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-ia-backfill",
        )
        draws = parse_iowa_winning_numbers_page(raw_html, game.slug)
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
        and jurisdiction_code == "in"
        and game.slug in _INDIANA_DRAW_PAGE_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-in-backfill",
        )
        draws = parse_indiana_draw_page(raw_html, game.slug)
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
        and jurisdiction_code == "il"
        and game.slug in _ILLINOIS_RESULTS_PAGE_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-il-backfill",
        )
        draws = parse_illinois_results_page(raw_html, game.slug)
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
        and jurisdiction_code == "id"
        and game.slug in _IDAHO_DRAW_PAGE_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-id-backfill",
        )
        draws = parse_idaho_draw_page(raw_html, game.slug)
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
        and jurisdiction_code == "ga"
        and game.slug in _GEORGIA_DRAW_GAMES
    ):
        raw_json, source_url = _georgia_draw_games_source(
            game,
            source_dir=None,
        )
        draws = parse_georgia_draw_games_json(raw_json, game.slug)
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
    if (
        source_file is None
        and jurisdiction_code == "de"
        and game.slug in _DELAWARE_SEARCH_WINNERS_GAMES
    ):
        raw_html, source_url = _delaware_search_winners_source(
            game,
            source_dir=None,
        )
        draws = parse_delaware_search_winners(raw_html, game.slug)
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
        and jurisdiction_code == "ct"
        and game.slug in _CONNECTICUT_WINNING_NUMBERS_GAMES
    ):
        raw_html, source_url = _connecticut_winning_numbers_draws_source(
            game,
            source_dir=None,
        )
        draws = parse_connecticut_winning_numbers(raw_html, game.slug)
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
        and jurisdiction_code == "co"
        and game.slug in _COLORADO_DRAWING_HISTORY_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-co-backfill",
        )
        draws = parse_colorado_drawing_history(raw_html, game.slug)
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
        and jurisdiction_code == "ar"
        and game.slug in _ARKANSAS_DID_I_WIN_GAMES
    ):
        raw_html, source_url = _read_source(
            game.source_url,
            None,
            f"{game.slug}-ar-backfill",
        )
        draws = parse_arkansas_did_i_win(raw_html, game.slug)
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
        and jurisdiction_code == "az"
        and game.slug in _ARIZONA_PAST_180_GAMES
    ):
        raw_text, source_url, draws = _arizona_past_180_draws(
            game,
            source_dir=None,
        )
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_text, draws)
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
    if (
        jurisdiction_code in _OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS
        and game.slug in _OFFICIAL_NATIONAL_RESULTS_GAMES
    ):
        raw_html, source_url = _read_source(game.source_url, source_dir, game.slug)
        draws = parse_official_national_results_page(raw_html, game.slug)
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
    if jurisdiction_code == "az" and game.slug in _ARIZONA_PAST_180_GAMES:
        raw_text, source_url, draws = _arizona_past_180_draws(
            game,
            source_dir=source_dir,
        )
        _insert_snapshot(conn, jurisdiction_code, game.slug, source_url, raw_text, draws)
        _replace_draw_results(conn, jurisdiction_code, game.slug, draws)
        conn.commit()
        return FetchResult(
            game_name=game.name,
            source_url=source_url,
            draw_count=len(draws),
            prize_row_count=sum(len(draw.prizes) for draw in draws),
            page_count=1,
        )
    if jurisdiction_code == "ar" and game.slug in _ARKANSAS_DID_I_WIN_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-ar-backfill",
        )
        draws = parse_arkansas_did_i_win(raw_html, game.slug)
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
    if jurisdiction_code == "co" and game.slug in _COLORADO_DRAWING_HISTORY_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-co-backfill",
        )
        draws = parse_colorado_drawing_history(raw_html, game.slug)
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
    if jurisdiction_code == "ct" and game.slug in _CONNECTICUT_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _connecticut_winning_numbers_draws_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_connecticut_winning_numbers(raw_html, game.slug)
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
    if jurisdiction_code == "de" and game.slug in _DELAWARE_SEARCH_WINNERS_GAMES:
        raw_html, source_url = _delaware_search_winners_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_delaware_search_winners(raw_html, game.slug)
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
    if jurisdiction_code == "ga" and game.slug in _GEORGIA_DRAW_GAMES:
        raw_json, source_url = _georgia_draw_games_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_georgia_draw_games_json(raw_json, game.slug)
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
    if jurisdiction_code == "id" and game.slug in _IDAHO_DRAW_PAGE_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-id-backfill",
        )
        draws = parse_idaho_draw_page(raw_html, game.slug)
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
    if jurisdiction_code == "il" and game.slug in _ILLINOIS_RESULTS_PAGE_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-il-backfill",
        )
        draws = parse_illinois_results_page(raw_html, game.slug)
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
    if jurisdiction_code == "in" and game.slug in _INDIANA_DRAW_PAGE_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-in-backfill",
        )
        draws = parse_indiana_draw_page(raw_html, game.slug)
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
    if jurisdiction_code == "ia" and game.slug in _IOWA_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-ia-backfill",
        )
        draws = parse_iowa_winning_numbers_page(raw_html, game.slug)
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
    if jurisdiction_code == "ky" and game.slug in _KENTUCKY_WINNING_NUMBERS_GAMES:
        raw_json, source_url = _kentucky_winning_numbers_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_kentucky_winning_numbers_json(raw_json, game.slug)
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
    if jurisdiction_code == "la" and game.slug in _LOUISIANA_LATEST_DRAW_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-la-backfill",
        )
        draws = parse_louisiana_latest_draw_page(raw_html, game.slug)
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
    if jurisdiction_code == "me" and game.slug in _MAINE_HOME_PAGE_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-me-backfill",
        )
        draws = parse_maine_home_page(raw_html, game.slug)
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
    if jurisdiction_code == "md" and game.slug in _MARYLAND_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-md-backfill",
        )
        draws = parse_maryland_winning_numbers_page(raw_html, game.slug)
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
    if jurisdiction_code == "ma" and game.slug in _MASSACHUSETTS_DRAW_RESULTS_GAMES:
        raw_json, source_url = _massachusetts_draw_results_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_massachusetts_draw_results_json(raw_json, game.slug)
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
    if jurisdiction_code == "mi" and game.slug in _MICHIGAN_DRAW_HISTORY_GAMES:
        raw_json, source_url = _michigan_draw_history_source(
            game,
            source_dir=source_dir,
        )
        draws = parse_michigan_draw_history_json(raw_json, game.slug)
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
    if jurisdiction_code == "mn" and game.slug in _MINNESOTA_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-mn-backfill",
        )
        draws = parse_minnesota_winning_numbers_page(raw_html, game.slug)
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
    if jurisdiction_code == "ms" and game.slug in _MISSISSIPPI_HOME_PAGE_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-ms-backfill",
        )
        draws = parse_mississippi_home_page(raw_html, game.slug)
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
    if jurisdiction_code == "mo" and game.slug in _MISSOURI_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-mo-backfill",
        )
        draws = parse_missouri_winning_numbers_page(raw_html, game.slug)
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
    if jurisdiction_code == "mt" and game.slug in _MONTANA_WINNING_NUMBERS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-mt-backfill",
        )
        draws = parse_montana_winning_numbers_table(raw_html, game.slug)
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
    if jurisdiction_code == "ne" and game.slug in _NEBRASKA_DRAW_RESULTS_GAMES:
        raw_html, source_url = _read_source(
            game.source_url,
            source_dir,
            f"{game.slug}-ne-backfill",
        )
        draws = parse_nebraska_draw_results_page(raw_html, game.slug)
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


def _arizona_past_180_draws(
    game: GameMetadata,
    *,
    source_dir: Path | None,
) -> tuple[str, str, tuple[ParsedDraw, ...]]:
    raw_text, source_url = _read_arizona_past_180_source(game, source_dir)
    return raw_text, source_url, parse_arizona_past_180_text(raw_text, game.slug)


def parse_past_drawings(raw_html: str) -> tuple[ParsedDraw, ...]:
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.table-viewport-large"):
        draw = _parse_large_table(table)
        if draw is not None:
            draws.append(draw)
    return tuple(draws)


def parse_official_national_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _OFFICIAL_NATIONAL_RESULTS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        match = _NATIONAL_DRAW_DATE_RE.match(lines[index])
        if match is None:
            index += 1
            continue

        numbers = _national_result_numbers(lines[index][match.end() :])
        cursor = index + 1
        while cursor < len(lines) and len(numbers) < 6:
            if _NATIONAL_DRAW_DATE_RE.match(lines[cursor]) is not None:
                break
            numbers.extend(_national_result_numbers(lines[cursor]))
            cursor += 1
        if len(numbers) >= 6:
            draws.append(
                ParsedDraw(
                    draw_date=_national_draw_date(match),
                    winning_number=", ".join(
                        (
                            *numbers[:5],
                            f"{numbers[5]} {special_number_name}",
                        )
                    ),
                    prizes=(),
                )
            )
        index = max(cursor, index + 1)
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


def parse_arizona_past_180_text(
    raw_text: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ARIZONA_PAST_180_GAMES[game_slug]
    special_label = "MEGA BALL" if game_slug == "mega-millions" else "POWER BALL"
    entry_re = re.compile(
        rf"DRAW DATE\s+(?P<date>\d{{4}}-\d{{2}}-\d{{2}}).*?"
        rf"WINNING NUMBERS\s+(?P<numbers>\d{{1,2}}\s*-\s*\d{{1,2}}\s*-\s*"
        rf"\d{{1,2}}\s*-\s*\d{{1,2}}\s*-\s*\d{{1,2}}).*?"
        rf"{special_label}\s+(?P<special>\d{{1,2}})",
        re.DOTALL,
    )
    draws: list[ParsedDraw] = []
    for match in entry_re.finditer(raw_text):
        draw_date = _arizona_draw_date(match.group("date"))
        if draw_date is None:
            continue
        numbers = re.findall(r"\d{1,2}", match.group("numbers"))
        special_number = match.group("special")
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _arizona_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_arkansas_did_i_win(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ARKANSAS_DID_I_WIN_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if len(cells) < 7:
            continue
        draw_date = _arkansas_draw_date(cells[0])
        if draw_date is None:
            continue
        numbers = tuple(cells[1:6])
        special_number = cells[6]
        if not all(re.fullmatch(r"\d{1,2}", value) for value in (*numbers, special_number)):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _arkansas_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_colorado_drawing_history(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    numbers_label, special_number_name = _COLORADO_DRAWING_HISTORY_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    lines = _page_lines(soup)
    draws: list[ParsedDraw] = []
    index = 0
    while index < len(lines):
        draw_date = _colorado_draw_date(lines[index])
        if draw_date is None:
            index += 1
            continue
        cursor = index + 1
        while cursor < len(lines) and lines[cursor] != numbers_label:
            if _colorado_draw_date(lines[cursor]) is not None:
                break
            cursor += 1
        if cursor + 2 >= len(lines) or lines[cursor] != numbers_label:
            index += 1
            continue
        numbers = re.findall(r"\d{1,2}", lines[cursor + 1])
        special_number = re.fullmatch(r"\d{1,2}", lines[cursor + 2])
        if len(numbers) == 5 and special_number is not None:
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(
                        [
                            *numbers,
                            f"{special_number.group(0)} {special_number_name}",
                        ]
                    ),
                    prizes=(),
                )
            )
        index = cursor + 3
    return tuple(draws)


def _colorado_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A, %m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


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


def parse_connecticut_winning_numbers(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, _, special_number_name = _CONNECTICUT_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("#gvWinningNumbers tbody tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all("td")]
        if not cells:
            continue
        if game_slug == "powerball":
            if len(cells) < 4 or cells[0] != "Powerball":
                continue
            raw_date, raw_numbers, raw_special = cells[1], cells[2], cells[3]
        else:
            if len(cells) < 3:
                continue
            raw_date, raw_numbers, raw_special = cells[0], cells[1], cells[2]
        draw_date = _connecticut_draw_date(raw_date)
        numbers = re.findall(r"\d{1,2}", raw_numbers)
        special_number = re.search(r"\d{1,2}", raw_special)
        if draw_date is None or len(numbers) != 5 or special_number is None:
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


def _connecticut_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_delaware_search_winners(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, game_name, special_number_name = _DELAWARE_SEARCH_WINNERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("table.table-winning-numbers-search-results tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        row_game = _delaware_row_game(cells[0])
        if row_game != game_name:
            continue
        draw_date = _delaware_draw_date(cells[1].get_text(" ", strip=True))
        numbers = [item.get_text(" ", strip=True) for item in cells[2].select("li")]
        if draw_date is None or len(numbers) != 6:
            continue
        primary_numbers = [number for number in numbers[:5] if re.fullmatch(r"\d{1,2}", number)]
        special_number = numbers[5]
        if len(primary_numbers) != 5 or not re.fullmatch(r"\d{1,2}", special_number):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _delaware_row_game(cell: Tag) -> str:
    for text in cell.stripped_strings:
        return text
    return ""


def _delaware_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_georgia_draw_games_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_name, special_prefix, special_number_name = _GEORGIA_DRAW_GAMES[game_slug]
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("draws") or ():
        if item.get("gameName") != game_name:
            continue
        if item.get("status") == "OPEN":
            continue
        draw_date = _georgia_draw_date(item.get("closeTime"))
        numbers = _georgia_draw_numbers(item, special_prefix, special_number_name)
        if draw_date is None or numbers is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(numbers),
                prizes=(),
            )
        )
    return tuple(draws)


def _georgia_draw_numbers(
    item: dict[str, object],
    special_prefix: str,
    special_number_name: str,
) -> tuple[str, ...] | None:
    results = item.get("results")
    if not isinstance(results, list) or not results:
        return None
    first_result = results[0]
    if not isinstance(first_result, dict):
        return None
    raw_numbers = first_result.get("primary")
    if not isinstance(raw_numbers, list):
        return None
    primary_numbers = [
        str(number)
        for number in raw_numbers
        if isinstance(number, str) and re.fullmatch(r"\d{1,2}", number)
    ][:5]
    special_marker = next(
        (
            number
            for number in raw_numbers
            if isinstance(number, str) and number.startswith(f"{special_prefix}-")
        ),
        None,
    )
    if len(primary_numbers) != 5 or special_marker is None:
        return None
    special_number = special_marker.split("-", 1)[1]
    if not re.fullmatch(r"\d{1,2}", special_number):
        return None
    return (*primary_numbers, f"{special_number} {special_number_name}")


def _georgia_draw_date(raw_value: object) -> str | None:
    milliseconds = _int_value(raw_value)
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=UTC,
    ).astimezone(_GEORGIA_TIMEZONE).strftime(_DRAW_DATE_FORMAT)


def parse_idaho_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _IDAHO_DRAW_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("tr"):
        date_cell = row.find("td", attrs={"data-title": "Date"})
        numbers_cell = row.find("td", attrs={"data-title": "Winning Numbers"})
        if date_cell is None or numbers_cell is None:
            continue
        draw_date = _idaho_draw_date(date_cell.get_text(" ", strip=True))
        numbers = [
            item.get_text(" ", strip=True)
            for item in numbers_cell.select("li")
        ]
        if draw_date is None or len(numbers) != 6:
            continue
        primary_numbers = [
            number for number in numbers[:5] if re.fullmatch(r"\d{1,2}", number)
        ]
        special_number = numbers[5]
        if len(primary_numbers) != 5 or not re.fullmatch(r"\d{1,2}", special_number):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _idaho_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_illinois_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _ILLINOIS_RESULTS_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for item in soup.select("li"):
        draw = _parse_illinois_result_line(
            item.get_text(" ", strip=True),
            special_number_name,
        )
        if draw is not None:
            draws.append(draw)
    return tuple(draws)


def _parse_illinois_result_line(
    line: str,
    special_number_name: str,
) -> ParsedDraw | None:
    match = re.search(
        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"([A-Z][a-z]+)\s+(\d{1,2}),\s+(\d{4})\b",
        line,
    )
    if match is None:
        return None
    numbers = re.findall(r"\b\d{1,2}\b", line[match.end() :])
    if len(numbers) < 6:
        return None
    draw_date = _illinois_draw_date(match.group(0))
    if draw_date is None:
        return None
    return ParsedDraw(
        draw_date=draw_date,
        winning_number=", ".join(
            [*numbers[:5], f"{numbers[5]} {special_number_name}"]
        ),
        prizes=(),
    )


def _illinois_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A %B %d, %Y").strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None


def parse_indiana_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _INDIANA_DRAW_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    section = soup.select_one("section.drawing-numbers")
    if section is None:
        return ()
    date_node = section.select_one(".sub-title")
    numbers_container = section.select_one(".numbers-container")
    if date_node is None or numbers_container is None:
        return ()
    draw_date = _indiana_draw_date(date_node.get_text(" ", strip=True))
    numbers = [
        item.get_text(" ", strip=True)
        for item in numbers_container.select(".winning-number")
    ]
    if draw_date is None or len(numbers) != 6:
        return ()
    primary_numbers = [
        number for number in numbers[:5] if re.fullmatch(r"\d{1,2}", number)
    ]
    special_number = numbers[5]
    if len(primary_numbers) != 5 or not re.fullmatch(r"\d{1,2}", special_number):
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*primary_numbers, f"{special_number} {special_number_name}"]
            ),
            prizes=(),
        ),
    )


def _indiana_draw_date(raw_value: str) -> str | None:
    cleaned = re.sub(r"(\d{1,2})(st|nd|rd|th)\b", r"\1", raw_value)
    try:
        parsed_date = datetime.strptime(
            f"{cleaned}, {date.today().year}",
            "%A, %B %d, %Y",
        )
    except ValueError:
        return None
    return parsed_date.strftime(_DRAW_DATE_FORMAT)


def parse_iowa_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    draw_index, special_number_name = _IOWA_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    matches = tuple(
        re.finditer(
            r"Drawing Date:\s*(\d{1,2})/(\d{1,2}):\s*"
            r"(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*"
            r"(\d{1,2})\s*-\s*(\d{1,2})\s+(\d{1,2})",
            text,
        )
    )
    if draw_index >= len(matches):
        return ()
    match = matches[draw_index]
    draw_date = _iowa_draw_date(match.group(1), match.group(2))
    if draw_date is None:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [
                    match.group(3),
                    match.group(4),
                    match.group(5),
                    match.group(6),
                    match.group(7),
                    f"{match.group(8)} {special_number_name}",
                ]
            ),
            prizes=(),
        ),
    )


def _iowa_draw_date(raw_month: str, raw_day: str) -> str | None:
    try:
        return datetime(
            date.today().year,
            int(raw_month),
            int(raw_day),
        ).strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_kentucky_winning_numbers_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, special_key, special_number_name = _KENTUCKY_WINNING_NUMBERS_GAMES[game_slug]
    payload = json.loads(raw_json)
    draws: list[ParsedDraw] = []
    for item in payload.get("DRAW_HISTORY") or ():
        draw_date = _kentucky_draw_date(item.get("DRAW_DATE"))
        primary_numbers = _kentucky_primary_numbers(item.get("DRAW_VALUES"))
        special_number = _kentucky_special_number(item, special_key)
        if draw_date is None or primary_numbers is None or special_number is None:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _kentucky_primary_numbers(raw_values: object) -> tuple[str, ...] | None:
    if not isinstance(raw_values, list):
        return None
    sorted_values = sorted(
        (
            value
            for value in raw_values
            if isinstance(value, dict)
            and _int_value(value.get("DRAW_NUMBER_POSITION")) is not None
            and _int_value(value.get("DRAW_VALUE")) is not None
        ),
        key=lambda value: int(value["DRAW_NUMBER_POSITION"]),
    )
    numbers = tuple(str(int(value["DRAW_VALUE"])) for value in sorted_values[:5])
    if len(numbers) != 5:
        return None
    return numbers


def _kentucky_special_number(item: dict[str, object], special_key: str) -> str | None:
    special_args = item.get("SPECIAL_ARGS")
    if not isinstance(special_args, dict):
        return None
    special_number = _int_value(special_args.get(special_key))
    if special_number is None:
        return None
    return str(special_number)


def _kentucky_draw_date(raw_value: object) -> str | None:
    milliseconds = _int_value(raw_value)
    if milliseconds is None:
        return None
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).strftime(
        _DRAW_DATE_FORMAT
    )


def parse_louisiana_latest_draw_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name = _LOUISIANA_LATEST_DRAW_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    content = soup.select_one("main") or soup
    date_match = re.search(
        r"View Latest Draw:\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
        content.get_text(" ", strip=True),
    )
    numbers = [
        item.get_text(" ", strip=True)
        for item in content.select("li")
        if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
    ][:6]
    if date_match is None or len(numbers) != 6:
        return ()
    draw_date = _louisiana_draw_date(date_match.group(1))
    if draw_date is None:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*numbers[:5], f"{numbers[5]} {special_number_name}"]
            ),
            prizes=(),
        ),
    )


def _louisiana_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%B %d, %Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_maine_home_page(raw_html: str, game_slug: str) -> tuple[ParsedDraw, ...]:
    game_label, special_number_name = _MAINE_HOME_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    image = soup.find("img", alt=re.compile(rf"^{re.escape(game_label)}$", re.I))
    if not isinstance(image, Tag):
        return ()
    block = _maine_game_block_text(image)
    date_match = re.search(r"\b[A-Z][a-z]+ \d{2}/\d{2}/\d{4}\b", block)
    if date_match is None:
        return ()
    numbers = [
        number
        for number in re.findall(r"\b\d{1,2}\b", block[date_match.end() :])
    ][:6]
    if len(numbers) != 6:
        return ()
    draw_date = _maine_draw_date(date_match.group(0))
    if draw_date is None:
        return ()
    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*numbers[:5], f"{numbers[5]} {special_number_name}"]
            ),
            prizes=(),
        ),
    )


def _maine_game_block_text(image: Tag) -> str:
    parts: list[str] = []
    for node in image.next_elements:
        if isinstance(node, Tag) and node.name == "img":
            break
        if isinstance(node, NavigableString):
            text = str(node).strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _maine_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%A %m/%d/%Y").strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None


def parse_maryland_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_label, special_number_name = _MARYLAND_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    heading = soup.find(string=re.compile(rf"^\s*{re.escape(game_label)}\s*$", re.I))
    if heading is None:
        return ()
    table = (
        heading.find_parent().find_next("table")
        if isinstance(heading, NavigableString)
        else None
    )
    if not isinstance(table, Tag):
        return ()
    draws: list[ParsedDraw] = []
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        draw_date = _maryland_draw_date(cells[0].get_text(" ", strip=True))
        primary_numbers = [
            item.get_text(" ", strip=True)
            for item in cells[1].select("li")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        special_numbers = [
            item.get_text(" ", strip=True)
            for item in cells[2].select("li")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        if draw_date is None or len(primary_numbers) != 5 or not special_numbers:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_numbers[0]} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _maryland_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m/%d/%y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_massachusetts_draw_results_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_identifier, special_key, special_number_name = (
        _MASSACHUSETTS_DRAW_RESULTS_GAMES[game_slug]
    )
    payload = json.loads(raw_json)
    raw_draws = payload.get("winningNumbers") if isinstance(payload, dict) else None
    if not isinstance(raw_draws, list):
        return ()

    draws: list[ParsedDraw] = []
    for item in raw_draws:
        if not isinstance(item, dict):
            continue
        if item.get("gameIdentifier") != game_identifier:
            continue
        if item.get("status") != "COMPLETE":
            continue

        draw_date = _massachusetts_draw_date(item.get("drawDate"))
        raw_numbers = item.get("winningNumbers")
        extras = item.get("extras")
        if not isinstance(raw_numbers, list) or not isinstance(extras, dict):
            continue

        primary_numbers = [
            str(number)
            for raw_number in raw_numbers[:5]
            if (number := _int_value(raw_number)) is not None
        ]
        special_number = _int_value(extras.get(special_key))
        if draw_date is None or len(primary_numbers) != 5 or special_number is None:
            continue

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [
                        *primary_numbers,
                        f"{special_number} {special_number_name}",
                    ]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _massachusetts_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_michigan_draw_history_json(
    raw_json: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    _, special_key, special_number_name = _MICHIGAN_DRAW_HISTORY_GAMES[game_slug]
    payload = json.loads(raw_json)
    game_data = payload.get("data", {}).get("gameByCode") if isinstance(payload, dict) else None
    if not isinstance(game_data, dict):
        return ()
    raw_draws = game_data.get("drawResultsBetweenDates")
    if not isinstance(raw_draws, list):
        return ()

    draws: list[ParsedDraw] = []
    for item in raw_draws:
        if not isinstance(item, dict):
            continue
        if _int_value(item.get("drawSequence")) != 1:
            continue

        winning_numbers = item.get("winningNumbers")
        if not isinstance(winning_numbers, dict):
            continue
        raw_numbers = winning_numbers.get("drawNumbers")
        if not isinstance(raw_numbers, list):
            continue
        primary_numbers = [
            str(number)
            for raw_number in raw_numbers[:5]
            if (number := _int_value(raw_number)) is not None
        ]
        special_number = _int_value(winning_numbers.get(special_key))
        draw_date = _michigan_draw_date(item.get("drawDate"))
        if draw_date is None or len(primary_numbers) != 5 or special_number is None:
            continue

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*primary_numbers, f"{special_number} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _michigan_draw_date(raw_value: object) -> str | None:
    if not isinstance(raw_value, str) or not raw_value:
        return None
    try:
        return datetime.fromisoformat(raw_value.replace("Z", "+00:00")).strftime(
            _DRAW_DATE_FORMAT
        )
    except ValueError:
        return None


def parse_minnesota_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_label, special_number_name = _MINNESOTA_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for card in soup.select("figure.card--winning-numbers"):
        heading = card.select_one("h4")
        if heading is None:
            continue
        if heading.get_text(" ", strip=True) != game_label:
            continue

        draw_date_node = card.select_one(".lottery-drawing span")
        draw_date = (
            _minnesota_draw_date(draw_date_node.get_text(" ", strip=True))
            if draw_date_node is not None
            else None
        )
        numbers = [
            item.get_text(" ", strip=True)
            for item in card.select(".lottery-number-list-item")
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        if draw_date is None or len(numbers) != 6:
            continue

        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers[:5], f"{numbers[5]} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _minnesota_draw_date(raw_value: str) -> str | None:
    normalized = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", raw_value)
    try:
        return datetime.strptime(normalized, "%B %d, %Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_mississippi_home_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_path, special_number_name = _MISSISSIPPI_HOME_PAGE_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    game_link = soup.select_one(f'a[href*="/games/{game_path}/"]')
    if game_link is None:
        return ()
    game_container = game_link.find_parent(
        class_=lambda value: value and "drawgamewrap" in value.split()
    )
    if not isinstance(game_container, Tag):
        return ()

    draw_date_node = game_container.select_one(".latestdraw")
    number_container = game_container.select_one(".lotto-numbers")
    if draw_date_node is None or number_container is None:
        return ()
    draw_date = _mississippi_draw_date(draw_date_node.get_text(" ", strip=True))
    numbers = [
        item.get_text(" ", strip=True)
        for item in number_container.select("i")
        if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
    ][:6]
    if draw_date is None or len(numbers) != 6:
        return ()

    return (
        ParsedDraw(
            draw_date=draw_date,
            winning_number=", ".join(
                [*numbers[:5], f"{numbers[5]} {special_number_name}"]
            ),
            prizes=(),
        ),
    )


def _mississippi_draw_date(raw_value: str) -> str | None:
    match = re.search(r"\b(\d{2}/\d{2})\b", raw_value)
    if match is None:
        return None
    try:
        return datetime.strptime(
            f"{match.group(1)}/{date.today().year}",
            "%m/%d/%Y",
        ).strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_missouri_winning_numbers_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_class, special_number_name = _MISSOURI_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for row in soup.select("table.table_game tbody tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        draw_date = _missouri_draw_date(cells[0].get_text(" ", strip=True))
        number_nodes = cells[1].select(".num_small")
        if len(number_nodes) < 6:
            continue
        special_node = number_nodes[5]
        if special_class not in special_node.get("class", ()):
            continue
        numbers = [
            item.get_text(" ", strip=True)
            for item in number_nodes[:6]
            if re.fullmatch(r"\d{1,2}", item.get_text(" ", strip=True))
        ]
        if draw_date is None or len(numbers) != 6:
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [*numbers[:5], f"{numbers[5]} {special_number_name}"]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


def _missouri_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%Y-%m-%d").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_montana_winning_numbers_table(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    special_number_name, required_headers = _MONTANA_WINNING_NUMBERS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    draws: list[ParsedDraw] = []
    for table in soup.select("table.winning-numbers-table"):
        headers = {
            header.get_text(" ", strip=True)
            for header in table.select("thead th")
            if header.get_text(" ", strip=True)
        }
        if not required_headers.issubset(headers):
            continue
        for row in table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            draw_date = _montana_draw_date(cells[0].get_text(" ", strip=True))
            primary_numbers = [
                number.strip()
                for number in cells[1].get_text(" ", strip=True).split(",")
                if re.fullmatch(r"\d{1,2}", number.strip())
            ]
            special_number = cells[2].get_text(" ", strip=True)
            if (
                draw_date is None
                or len(primary_numbers) != 5
                or re.fullmatch(r"\d{1,2}", special_number) is None
            ):
                continue
            draws.append(
                ParsedDraw(
                    draw_date=draw_date,
                    winning_number=", ".join(
                        [*primary_numbers, f"{special_number} {special_number_name}"]
                    ),
                    prizes=(),
                )
            )
    return tuple(draws)


def _montana_draw_date(raw_value: str) -> str | None:
    try:
        return datetime.strptime(raw_value, "%m.%d.%Y").strftime(_DRAW_DATE_FORMAT)
    except ValueError:
        return None


def parse_nebraska_draw_results_page(
    raw_html: str,
    game_slug: str,
) -> tuple[ParsedDraw, ...]:
    game_name, special_number_name = _NEBRASKA_DRAW_RESULTS_GAMES[game_slug]
    soup = BeautifulSoup(raw_html, "html.parser")
    heading = next(
        (
            heading
            for heading in soup.select("h3")
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
        if len(cells) < 3:
            continue
        draw_date = _nebraska_draw_date(cells[0].get_text(" ", strip=True))
        primary_numbers = [
            number
            for raw_number in cells[1].get_text(" ", strip=True).split(",")
            if (number := _nebraska_number(raw_number)) is not None
        ]
        special_number = _nebraska_number(cells[2].get_text(" ", strip=True))
        if (
            draw_date is None
            or len(primary_numbers) != 5
            or special_number is None
        ):
            continue
        draws.append(
            ParsedDraw(
                draw_date=draw_date,
                winning_number=", ".join(
                    [
                        *primary_numbers,
                        f"{special_number} {special_number_name}",
                    ]
                ),
                prizes=(),
            )
        )
    return tuple(draws)


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


def _national_result_numbers(value: str) -> list[str]:
    return re.findall(r"\b\d{1,2}\b", value)


def _national_draw_date(match: re.Match[str]) -> str:
    raw_date = f"{match.group(1)}, {match.group(2)} {match.group(3)}, {match.group(4)}"
    for date_format in ("%a, %B %d, %Y", "%a, %b %d, %Y"):
        try:
            return datetime.strptime(raw_date, date_format).strftime(_DRAW_DATE_FORMAT)
        except ValueError:
            pass
    raise ValueError(f"invalid draw date: {raw_date}")


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
    if (
        jurisdiction_code in _OFFICIAL_NATIONAL_RESULTS_JURISDICTIONS
        and game_slug in _OFFICIAL_NATIONAL_RESULTS_GAMES
    ):
        return parse_official_national_results_page(raw_html, game_slug)
    if jurisdiction_code == "ca" and game_slug == "hot-spot":
        return parse_california_hot_spot(raw_html)
    if jurisdiction_code == "ca" and game_slug in _CALIFORNIA_GAME_SLUGS:
        return parse_california_draw_game(raw_html)
    if jurisdiction_code == "ar" and game_slug in _ARKANSAS_DID_I_WIN_GAMES:
        return parse_arkansas_did_i_win(raw_html, game_slug)
    if jurisdiction_code == "co" and game_slug in _COLORADO_DRAWING_HISTORY_GAMES:
        return parse_colorado_drawing_history(raw_html, game_slug)
    if jurisdiction_code == "az" and game_slug in _ARIZONA_PAST_180_GAMES:
        return parse_arizona_past_180_text(raw_html, game_slug)
    if jurisdiction_code == "tx" and game_slug in _TEXAS_SPECIAL_NUMBER_NAMES:
        return parse_texas_winning_numbers(raw_html, game_slug)
    if jurisdiction_code == "ct" and game_slug in _CONNECTICUT_WINNING_NUMBERS_GAMES:
        return parse_connecticut_winning_numbers(raw_html, game_slug)
    if jurisdiction_code == "de" and game_slug in _DELAWARE_SEARCH_WINNERS_GAMES:
        return parse_delaware_search_winners(raw_html, game_slug)
    if jurisdiction_code == "ga" and game_slug in _GEORGIA_DRAW_GAMES:
        return parse_georgia_draw_games_json(raw_html, game_slug)
    if jurisdiction_code == "id" and game_slug in _IDAHO_DRAW_PAGE_GAMES:
        return parse_idaho_draw_page(raw_html, game_slug)
    if jurisdiction_code == "il" and game_slug in _ILLINOIS_RESULTS_PAGE_GAMES:
        return parse_illinois_results_page(raw_html, game_slug)
    if jurisdiction_code == "in" and game_slug in _INDIANA_DRAW_PAGE_GAMES:
        return parse_indiana_draw_page(raw_html, game_slug)
    if jurisdiction_code == "ia" and game_slug in _IOWA_WINNING_NUMBERS_GAMES:
        return parse_iowa_winning_numbers_page(raw_html, game_slug)
    if jurisdiction_code == "ky" and game_slug in _KENTUCKY_WINNING_NUMBERS_GAMES:
        return parse_kentucky_winning_numbers_json(raw_html, game_slug)
    if jurisdiction_code == "la" and game_slug in _LOUISIANA_LATEST_DRAW_GAMES:
        return parse_louisiana_latest_draw_page(raw_html, game_slug)
    if jurisdiction_code == "me" and game_slug in _MAINE_HOME_PAGE_GAMES:
        return parse_maine_home_page(raw_html, game_slug)
    if jurisdiction_code == "md" and game_slug in _MARYLAND_WINNING_NUMBERS_GAMES:
        return parse_maryland_winning_numbers_page(raw_html, game_slug)
    if jurisdiction_code == "ma" and game_slug in _MASSACHUSETTS_DRAW_RESULTS_GAMES:
        return parse_massachusetts_draw_results_json(raw_html, game_slug)
    if jurisdiction_code == "mi" and game_slug in _MICHIGAN_DRAW_HISTORY_GAMES:
        return parse_michigan_draw_history_json(raw_html, game_slug)
    if jurisdiction_code == "mn" and game_slug in _MINNESOTA_WINNING_NUMBERS_GAMES:
        return parse_minnesota_winning_numbers_page(raw_html, game_slug)
    if jurisdiction_code == "ms" and game_slug in _MISSISSIPPI_HOME_PAGE_GAMES:
        return parse_mississippi_home_page(raw_html, game_slug)
    if jurisdiction_code == "mo" and game_slug in _MISSOURI_WINNING_NUMBERS_GAMES:
        return parse_missouri_winning_numbers_page(raw_html, game_slug)
    if jurisdiction_code == "mt" and game_slug in _MONTANA_WINNING_NUMBERS_GAMES:
        return parse_montana_winning_numbers_table(raw_html, game_slug)
    if jurisdiction_code == "ne" and game_slug in _NEBRASKA_DRAW_RESULTS_GAMES:
        return parse_nebraska_draw_results_page(raw_html, game_slug)
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


def _read_arizona_past_180_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-az-backfill"
    if source_dir is not None:
        text_file = source_dir / f"{source_name}.txt"
        if text_file.exists():
            return text_file.read_text(encoding="utf-8"), text_file.as_uri()
        pdf_file = source_dir / f"{source_name}.pdf"
        return _extract_pdf_text(pdf_file.read_bytes()), pdf_file.as_uri()

    response = httpx.get(game.source_url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    return _extract_pdf_text(response.content), str(response.url)


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


def _connecticut_winning_numbers_draws_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    game_id, page_name, _ = _CONNECTICUT_WINNING_NUMBERS_GAMES[game.slug]
    source_name = f"{game.slug}-ct-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.html"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    end_date = date.today()
    start_date = date.fromordinal(end_date.toordinal() - 180)
    query = urlencode(
        {
            "g": game_id,
            "s": start_date.strftime("%m/%d/%Y"),
            "e": end_date.strftime("%m/%d/%Y"),
        }
    )
    source_url = f"https://www.ctlottery.org/ajax/getWinningNumbers?{query}"
    headers = {
        "Referer": f"https://www.ctlottery.org/WinningNumbers/{page_name}",
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }
    response = httpx.get(
        source_url,
        headers=headers,
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)


def _delaware_search_winners_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-de-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.html"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_path, _, _ = _DELAWARE_SEARCH_WINNERS_GAMES[game.slug]
    today = date.today()
    source_url = (
        "https://www.delottery.com/Winning-Numbers/Search-Winners/"
        f"{today.year}/{today.month}/{game_path}"
    )
    raw_html, resolved_url = _read_source(source_url, None, source_name)
    return raw_html, resolved_url


def _georgia_draw_games_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ga-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_name, _, _ = _GEORGIA_DRAW_GAMES[game.slug]
    query = urlencode(
        {
            "game-names": game_name,
            "previous-draws": "180",
            "page": "0",
            "size": "180",
        }
    )
    source_url = f"https://www.galottery.com/api/v2/draw-games/draws/page?{query}"
    return _read_source(source_url, None, source_name, suffix=".json")


def _kentucky_winning_numbers_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ky-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_number, _, _ = _KENTUCKY_WINNING_NUMBERS_GAMES[game.slug]
    source_url = "https://www.kylottery.com/webhandlers/WinningNumbers.xhtml"
    payload = json.dumps({"gameNumber": game_number, "infoRequest": "11"})
    response = httpx.post(
        source_url,
        content=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)


def _massachusetts_draw_results_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-ma-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    source_url = "https://www.masslottery.com/api/v1/draw-results"
    return _read_source(source_url, None, source_name, suffix=".json")


def _michigan_draw_history_source(
    game: GameMetadata,
    source_dir: Path | None,
) -> tuple[str, str]:
    source_name = f"{game.slug}-mi-backfill"
    if source_dir is not None:
        source_file = source_dir / f"{source_name}.json"
        return source_file.read_text(encoding="utf-8"), source_file.as_uri()

    game_code, _, _ = _MICHIGAN_DRAW_HISTORY_GAMES[game.slug]
    end_date = datetime.now(tz=UTC)
    start_date = datetime.fromordinal(end_date.date().toordinal() - 180).replace(
        tzinfo=UTC
    )
    source_url = "https://www.michiganlottery.com/api"
    payload = json.dumps(
        {
            "query": _MICHIGAN_DRAW_HISTORY_QUERY,
            "variables": {
                "gameCode": game_code,
                "startDateString": start_date.isoformat().replace("+00:00", "Z"),
                "endDateString": end_date.isoformat().replace("+00:00", "Z"),
            },
        }
    )
    response = httpx.post(
        source_url,
        content=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        follow_redirects=True,
        timeout=30,
    )
    response.raise_for_status()
    return response.text, str(response.url)


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
