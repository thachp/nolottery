from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from .metadata import DEFAULT_GAMES, GameMetadata, PrizeTier, WagerOption

_DRAW_DATE_FORMAT = "%a, %b %d, %Y"


@dataclass(frozen=True)
class StoredDraw:
    game_slug: str
    game_name: str
    draw_date: str
    winning_number: str


def database_path(data_dir: Path) -> Path:
    return data_dir / "lottery.sqlite3"


def connect(data_dir: Path) -> sqlite3.Connection:
    data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path(data_dir))
    conn.row_factory = sqlite3.Row
    initialize(conn)
    seed_default_metadata(conn)
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists games (
            slug text primary key,
            name text not null,
            source_url text not null,
            reviewed_on text not null
        );

        create table if not exists wager_options (
            game_slug text not null references games(slug),
            option_slug text not null,
            label text not null,
            ticket_cost real not null,
            primary key (game_slug, option_slug)
        );

        create table if not exists prize_tiers (
            game_slug text not null references games(slug),
            option_slug text not null,
            label text not null,
            probability real not null,
            prize real not null,
            primary key (game_slug, option_slug, label)
        );

        create table if not exists fetch_snapshots (
            id integer primary key autoincrement,
            game_slug text not null references games(slug),
            source_url text not null,
            fetched_at text not null,
            raw_html text not null,
            parsed_json text not null
        );

        create table if not exists draw_results (
            id integer primary key autoincrement,
            game_slug text not null references games(slug),
            draw_date text not null,
            winning_number text not null,
            prize_amount real not null,
            wa_winners integer not null,
            total real not null
        );

        create table if not exists ledger_entries (
            id integer primary key autoincrement,
            purchase_date text not null,
            game_slug text not null,
            draw_date text not null,
            ticket_cost real not null,
            prize_won real not null,
            draw_id text,
            bet_type text,
            number_selection text,
            recommended_by_app integer not null default 0,
            store_name text,
            notes text
        );
        """
    )
    conn.commit()


def seed_default_metadata(conn: sqlite3.Connection) -> None:
    for game in DEFAULT_GAMES.values():
        conn.execute(
            """
            insert into games (slug, name, source_url, reviewed_on)
            values (?, ?, ?, ?)
            on conflict(slug) do update set
                name = excluded.name,
                source_url = excluded.source_url,
                reviewed_on = excluded.reviewed_on
            """,
            (
                game.slug,
                game.name,
                game.source_url,
                game.reviewed_on,
            ),
        )
        option_slugs = tuple(option.slug for option in game.wager_options)
        if option_slugs:
            placeholders = ", ".join("?" for _ in option_slugs)
            conn.execute(
                f"""
                delete from wager_options
                where game_slug = ? and option_slug not in ({placeholders})
                """,
                (game.slug, *option_slugs),
            )
            conn.execute(
                f"""
                delete from prize_tiers
                where game_slug = ? and option_slug not in ({placeholders})
                """,
                (game.slug, *option_slugs),
            )
        for option in game.wager_options:
            conn.execute(
                """
                insert into wager_options (game_slug, option_slug, label, ticket_cost)
                values (?, ?, ?, ?)
                on conflict(game_slug, option_slug) do update set
                    label = excluded.label,
                    ticket_cost = excluded.ticket_cost
                """,
                (game.slug, option.slug, option.label, option.ticket_cost),
            )
            tier_labels = tuple(tier.label for tier in option.prize_tiers)
            if tier_labels:
                placeholders = ", ".join("?" for _ in tier_labels)
                conn.execute(
                    f"""
                    delete from prize_tiers
                    where game_slug = ?
                        and option_slug = ?
                        and label not in ({placeholders})
                    """,
                    (game.slug, option.slug, *tier_labels),
                )
            for tier in option.prize_tiers:
                conn.execute(
                    """
                    insert into prize_tiers (game_slug, option_slug, label, probability, prize)
                    values (?, ?, ?, ?, ?)
                    on conflict(game_slug, option_slug, label) do update set
                        probability = excluded.probability,
                        prize = excluded.prize
                    """,
                    (game.slug, option.slug, tier.label, tier.probability, tier.prize),
                )
    conn.commit()


def get_game(conn: sqlite3.Connection, slug: str) -> GameMetadata | None:
    game = conn.execute(
        "select slug, name, source_url, reviewed_on from games where slug = ?",
        (slug,),
    ).fetchone()
    if game is None:
        return None

    options = conn.execute(
        """
        select option_slug, label, ticket_cost
        from wager_options
        where game_slug = ?
        order by option_slug
        """,
        (slug,),
    ).fetchall()
    wager_options = []
    for option in options:
        tiers = conn.execute(
            """
            select label, probability, prize
            from prize_tiers
            where game_slug = ? and option_slug = ?
            order by prize desc
            """,
            (slug, option["option_slug"]),
        ).fetchall()
        wager_options.append(
            WagerOption(
                slug=option["option_slug"],
                label=option["label"],
                ticket_cost=option["ticket_cost"],
                prize_tiers=tuple(
                    PrizeTier(
                        label=tier["label"],
                        probability=tier["probability"],
                        prize=tier["prize"],
                    )
                    for tier in tiers
                ),
            )
        )

    return GameMetadata(
        slug=game["slug"],
        name=game["name"],
        source_url=game["source_url"],
        reviewed_on=game["reviewed_on"],
        wager_options=tuple(wager_options),
    )


def list_game_slugs(conn: sqlite3.Connection) -> tuple[str, ...]:
    rows = conn.execute("select slug from games order by slug").fetchall()
    return tuple(row["slug"] for row in rows)


def recent_draws(
    conn: sqlite3.Connection,
    game_slug: str,
    *,
    limit: int,
) -> tuple[StoredDraw, ...]:
    rows = conn.execute(
        """
        select
            min(draw_results.id) as first_id,
            draw_results.game_slug,
            games.name as game_name,
            draw_results.draw_date,
            draw_results.winning_number
        from draw_results
        join games on games.slug = draw_results.game_slug
        where draw_results.game_slug = ?
        group by
            draw_results.game_slug,
            games.name,
            draw_results.draw_date,
            draw_results.winning_number
        """,
        (game_slug,),
    ).fetchall()
    sorted_rows = sorted(
        rows,
        key=lambda row: _draw_sort_key(row["draw_date"], row["first_id"]),
        reverse=True,
    )
    return tuple(
        StoredDraw(
            game_slug=row["game_slug"],
            game_name=row["game_name"],
            draw_date=row["draw_date"],
            winning_number=row["winning_number"],
        )
        for row in sorted_rows[:limit]
    )


def _draw_sort_key(draw_date: str, first_id: int) -> tuple[bool, date, int]:
    try:
        parsed = datetime.strptime(draw_date, _DRAW_DATE_FORMAT).date()
    except ValueError:
        return (False, date.min, first_id)
    return (True, parsed, first_id)
