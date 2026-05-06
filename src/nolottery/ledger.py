from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerEntry:
    purchase_date: str
    game_slug: str
    draw_date: str
    ticket_cost: float
    prize_won: float
    draw_id: str | None = None
    bet_type: str | None = None
    number_selection: str | None = None
    recommended_by_app: bool = False
    store_name: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class LedgerSummary:
    tickets: int
    spent: float
    won: float

    @property
    def profit(self) -> float:
        return self.won - self.spent

    @property
    def roi_percent(self) -> float:
        if self.spent == 0:
            return 0.0
        return (self.profit / self.spent) * 100


def add_entry(conn: sqlite3.Connection, entry: LedgerEntry) -> None:
    conn.execute(
        """
        insert into ledger_entries (
            purchase_date,
            game_slug,
            draw_date,
            ticket_cost,
            prize_won,
            draw_id,
            bet_type,
            number_selection,
            recommended_by_app,
            store_name,
            notes
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry.purchase_date,
            entry.game_slug,
            entry.draw_date,
            entry.ticket_cost,
            entry.prize_won,
            entry.draw_id,
            entry.bet_type,
            entry.number_selection,
            1 if entry.recommended_by_app else 0,
            entry.store_name,
            entry.notes,
        ),
    )
    conn.commit()


def summarize(conn: sqlite3.Connection) -> LedgerSummary:
    row = conn.execute(
        """
        select
            count(*) as tickets,
            coalesce(sum(ticket_cost), 0) as spent,
            coalesce(sum(prize_won), 0) as won
        from ledger_entries
        """
    ).fetchone()
    return LedgerSummary(
        tickets=row["tickets"],
        spent=row["spent"],
        won=row["won"],
    )

