from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import db
from .ev import AnalysisResult, analyze_game
from .fetch import FetchResult, fetch_game, fetch_game_backfill
from .ledger import LedgerEntry
from .ledger import add_entry as add_ledger_entry
from .ledger import summarize as summarize_ledger
from .metadata import GameMetadata
from .recommend import Recommendation, displayed_hit_rate, recommend_highest_hit_rate
from .settings import AppSettings


app = typer.Typer(no_args_is_help=True)
ledger_app = typer.Typer(help="Track purchased tickets and realized winnings.")
app.add_typer(ledger_app, name="ledger")
console = Console()


def _data_dir_option() -> Path:
    return Path.home() / ".nolottery"


@app.callback()
def main(
    ctx: typer.Context,
    data_dir: Annotated[
        Path,
        typer.Option(
            "--data-dir",
            help="Directory for the local SQLite database and fetch cache.",
        ),
    ] = _data_dir_option(),
) -> None:
    ctx.obj = {"data_dir": data_dir}


@app.command()
def analyze(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as cashpop.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Analyze expected value for a supported Washington Lottery game."""
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = tuple(
            analyze_game(metadata, AppSettings()) for metadata in _load_games(conn)
        )
        if output == "json":
            console.print_json(
                json.dumps(
                    {"games": [_analysis_to_dict(result) for result in results]}
                )
            )
            return
        if output != "table":
            raise typer.BadParameter("output must be table or json")
        for result in results:
            _print_analysis_table(result)
        return

    metadata = db.get_game(conn, game)
    if metadata is None:
        raise typer.BadParameter(f"unknown game: {game}")

    result = analyze_game(metadata, AppSettings())
    if output == "json":
        console.print_json(json.dumps(_analysis_to_dict(result)))
        return
    if output != "table":
        raise typer.BadParameter("output must be table or json")

    _print_analysis_table(result)


@app.command()
def fetch(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as cashpop.")],
    source_file: Annotated[
        Path | None,
        typer.Option(
            "--source-file",
            help="Read an already downloaded official HTML page instead of making a network request.",
        ),
    ] = None,
    source_dir: Annotated[
        Path | None,
        typer.Option(
            "--source-dir",
            help="Read fixture HTML files from this directory.",
        ),
    ] = None,
    backfill: Annotated[
        bool,
        typer.Option(
            "--backfill",
            help="Fetch every available yearly past-drawings page.",
        ),
    ] = False,
) -> None:
    """Fetch official past drawing data and persist a local snapshot."""
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        if source_file is not None:
            raise typer.BadParameter("--source-file cannot be used with game 'all'")
        results = []
        for metadata in _load_games(conn):
            game_source_file = (
                source_dir / f"{metadata.slug}.html" if source_dir is not None else None
            )
            if backfill:
                results.append(fetch_game_backfill(conn, metadata, source_dir))
            else:
                results.append(fetch_game(conn, metadata, game_source_file))
        for result in results:
            _print_fetch_result(result)
        console.print(f"{len(results)} games fetched")
        return

    if source_dir is not None and not backfill:
        raise typer.BadParameter("--source-dir can only be used with game 'all' or --backfill")
    if source_file is not None and backfill:
        raise typer.BadParameter("--source-file cannot be used with --backfill")

    metadata = db.get_game(conn, game)
    if metadata is None:
        raise typer.BadParameter(f"unknown game: {game}")

    if backfill:
        result = fetch_game_backfill(conn, metadata, source_dir)
    else:
        result = fetch_game(conn, metadata, source_file)
    _print_fetch_result(result)


def _print_fetch_result(result: FetchResult) -> None:
    console.print(
        f"{result.game_name}: fetched {result.draw_count} draw"
        f"{'' if result.draw_count == 1 else 's'} and "
        f"{result.prize_row_count} prize rows"
        f" from {result.page_count} page"
        f"{'' if result.page_count == 1 else 's'}"
    )


@app.command()
def rank(ctx: typer.Context) -> None:
    """Rank supported games by best after-tax expected value."""
    conn = db.connect(ctx.obj["data_dir"])
    results = []
    for slug in db.list_game_slugs(conn):
        metadata = db.get_game(conn, slug)
        if metadata is not None:
            results.append(analyze_game(metadata, AppSettings()))
    results.sort(key=lambda result: result.best_option.net_after_tax_ev, reverse=True)

    table = Table()
    table.add_column("Rank", justify="right")
    table.add_column("Game", no_wrap=True)
    table.add_column("Best Wager")
    table.add_column("Decision")
    table.add_column("After-tax EV", justify="right", no_wrap=True)
    table.add_column("Net EV", justify="right", no_wrap=True)
    table.add_column("Hit Rate", justify="right", no_wrap=True)
    for index, result in enumerate(results, start=1):
        option = result.best_option
        table.add_row(
            str(index),
            result.game_name,
            option.option_label,
            result.decision,
            f"${option.after_tax_ev:.2f}",
            f"${option.net_after_tax_ev:.2f}",
            _format_probability(option.hit_rate),
        )
    console.print(table)


@app.command()
def recommend(
    ctx: typer.Context,
    budget: Annotated[
        float,
        typer.Option(
            "--budget",
            "-b",
            min=0.01,
            help="Maximum cost for one ticket/play recommendation.",
        ),
    ] = 1.0,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Recommend the highest hit-rate play style within a small budget."""
    conn = db.connect(ctx.obj["data_dir"])
    games = _load_games(conn)
    recommendations = recommend_highest_hit_rate(games, AppSettings(), budget)
    if not recommendations:
        raise typer.BadParameter("budget is below the cheapest supported wager")

    if output == "json":
        console.print_json(
            json.dumps(
                {
                    "budget": budget,
                    "best": _recommendation_to_dict(recommendations[0]),
                    "recommendations": [
                        _recommendation_to_dict(recommendation)
                        for recommendation in recommendations
                    ],
                }
            )
        )
        return
    if output != "table":
        raise typer.BadParameter("output must be table or json")

    _print_recommendation_table(recommendations, budget)


def _print_analysis_table(result: AnalysisResult) -> None:
    console.print(result.game_name)
    console.print(f"Decision: {result.decision}")
    console.print(f"Reason: {result.reason}")

    table = Table()
    table.add_column("Rank", justify="right")
    table.add_column("Wager", no_wrap=True)
    table.add_column("Gross EV", justify="right")
    table.add_column("After-tax EV", justify="right")
    table.add_column("Net EV", justify="right")
    table.add_column("Hit Rate", justify="right")
    table.add_column("Max Tickets", justify="right")
    for rank, option in enumerate(result.options, start=1):
        table.add_row(
            str(rank),
            option.option_label,
            f"${option.gross_ev:.2f}",
            f"${option.after_tax_ev:.2f}",
            f"${option.net_after_tax_ev:.2f}",
            _format_probability(option.hit_rate),
            str(option.max_recommended_tickets if result.decision == "PLAY" else 0),
        )
    console.print(table)


def _print_recommendation_table(
    recommendations: tuple[Recommendation, ...],
    budget: float,
) -> None:
    console.print(f"Highest hit-rate recommendations under ${budget:.2f}")
    table = Table()
    table.add_column("Rank", justify="right")
    table.add_column("Game", no_wrap=True)
    table.add_column("Wager")
    table.add_column("Cost", justify="right")
    table.add_column("Hit Rate", justify="right")
    table.add_column("Net EV", justify="right")
    table.add_column("Quick Pick Prediction")
    for rank, recommendation in enumerate(recommendations, start=1):
        option = recommendation.option
        table.add_row(
            str(rank),
            recommendation.game_name,
            option.option_label,
            f"${option.ticket_cost:.2f}",
            _format_probability(displayed_hit_rate(recommendation)),
            f"${option.net_after_tax_ev:.2f}",
            recommendation.prediction_label,
        )
    console.print(table)
    console.print(f"Recommended: {recommendations[0].reason}")
    console.print("Prediction method: quick-pick random; no odds advantage.")


def _analysis_to_dict(result: AnalysisResult) -> dict[str, object]:
    return {
        "game_slug": result.game_slug,
        "game": result.game_name,
        "decision": result.decision,
        "reason": result.reason,
        "best_option": result.best_option.option_label,
        "ticket_cost": result.best_option.ticket_cost,
        "gross_ev": result.best_option.gross_ev,
        "after_tax_ev": result.best_option.after_tax_ev,
        "net_after_tax_ev": result.best_option.net_after_tax_ev,
        "hit_rate": result.best_option.hit_rate,
        "max_recommended_tickets": (
            result.best_option.max_recommended_tickets
            if result.decision == "PLAY"
            else 0
        ),
        "options": [
            {
                "slug": option.option_slug,
                "label": option.option_label,
                "ticket_cost": option.ticket_cost,
                "gross_ev": option.gross_ev,
                "after_tax_ev": option.after_tax_ev,
                "net_after_tax_ev": option.net_after_tax_ev,
                "hit_rate": option.hit_rate,
            }
            for option in result.options
        ],
    }


def _recommendation_to_dict(recommendation: Recommendation) -> dict[str, object]:
    option = recommendation.option
    return {
        "game_slug": recommendation.game_slug,
        "game": recommendation.game_name,
        "option_slug": option.option_slug,
        "option": option.option_label,
        "ticket_cost": option.ticket_cost,
        "hit_rate": displayed_hit_rate(recommendation),
        "net_after_tax_ev": option.net_after_tax_ev,
        "number_selection": list(recommendation.number_selection),
        "number_selection_label": recommendation.number_selection_label,
        "prediction": list(recommendation.prediction),
        "prediction_label": recommendation.prediction_label,
        "prediction_method": recommendation.prediction_method,
        "reason": recommendation.reason,
    }


def _load_games(conn) -> tuple[GameMetadata, ...]:
    games = []
    for slug in db.list_game_slugs(conn):
        metadata = db.get_game(conn, slug)
        if metadata is not None:
            games.append(metadata)
    return tuple(games)


def _format_probability(probability: float) -> str:
    if probability <= 0:
        return "n/a"
    return f"1:{1 / probability:.2f}"


@ledger_app.command("add")
def ledger_add(ctx: typer.Context) -> None:
    """Prompt for one purchased ticket and store it in the local ledger."""
    entry = LedgerEntry(
        purchase_date=typer.prompt("Purchase date"),
        game_slug=typer.prompt("Game"),
        draw_date=typer.prompt("Draw date"),
        ticket_cost=typer.prompt("Ticket cost", type=float),
        prize_won=typer.prompt("Prize won", type=float),
        draw_id=_empty_to_none(typer.prompt("Draw ID", default="", show_default=False)),
        bet_type=_empty_to_none(
            typer.prompt("Bet type", default="", show_default=False)
        ),
        number_selection=_empty_to_none(
            typer.prompt("Number selection", default="", show_default=False)
        ),
        recommended_by_app=typer.confirm("Recommended by app?"),
        store_name=_empty_to_none(
            typer.prompt("Store name", default="", show_default=False)
        ),
        notes=_empty_to_none(typer.prompt("Notes", default="", show_default=False)),
    )
    conn = db.connect(ctx.obj["data_dir"])
    add_ledger_entry(conn, entry)
    console.print("Ticket recorded")


@ledger_app.command("summary")
def ledger_summary(ctx: typer.Context) -> None:
    """Summarize ledger spend, winnings, profit, and ROI."""
    conn = db.connect(ctx.obj["data_dir"])
    summary = summarize_ledger(conn)
    table = Table()
    table.add_column("Tickets", justify="right")
    table.add_column("Spent", justify="right")
    table.add_column("Won", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("ROI", justify="right")
    table.add_row(
        str(summary.tickets),
        f"${summary.spent:.2f}",
        f"${summary.won:.2f}",
        f"${summary.profit:.2f}",
        f"{summary.roi_percent:.2f}%",
    )
    console.print(table)


def _empty_to_none(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None
