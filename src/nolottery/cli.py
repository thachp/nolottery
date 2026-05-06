from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import db
from .audit import chi_square_audit, combination_audit, frequency_audit, gap_audit
from .cli_output import (
    format_probability,
    print_analysis_table,
    print_audit_summary_table,
    print_combination_audit_tables,
    print_draws_table,
    print_fetch_result,
    print_frequency_audit_tables,
    print_gap_audit_tables,
    print_low_share_table,
    print_openai_evaluation,
    print_recommendation_table,
)
from .cli_payloads import (
    analysis_to_dict,
    compact_audit,
    draws_to_dict,
    low_share_results_to_dict,
    openai_audit_payload,
    openai_low_share_payload,
    openai_recommendation_payload,
    recommendation_to_dict,
)
from .ev import analyze_game
from .fetch import fetch_game, fetch_game_backfill
from .ledger import LedgerEntry
from .ledger import add_entry as add_ledger_entry
from .ledger import summarize as summarize_ledger
from .low_share import generate_low_share_options
from .metadata import GameMetadata
from .openai_eval import DEFAULT_OPENAI_MODEL
from .openai_eval import OpenAIEvaluationError
from .openai_eval import evaluate_low_share_with_openai
from .openai_eval import evaluate_recommendations_with_openai
from .openai_eval import explain_audits_with_openai
from .recommend import recommend_highest_hit_rate
from .settings import AppSettings


app = typer.Typer(no_args_is_help=True)
audit_app = typer.Typer(help="Audit stored draw randomness statistics.")
ledger_app = typer.Typer(help="Track purchased tickets and realized winnings.")
app.add_typer(audit_app, name="audit")
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
                    {"games": [analysis_to_dict(result) for result in results]}
                )
            )
            return
        if output != "table":
            raise typer.BadParameter("output must be table or json")
        for result in results:
            print_analysis_table(console, result)
        return

    metadata = db.get_game(conn, game)
    if metadata is None:
        raise typer.BadParameter(f"unknown game: {game}")

    result = analyze_game(metadata, AppSettings())
    if output == "json":
        console.print_json(json.dumps(analysis_to_dict(result)))
        return
    if output != "table":
        raise typer.BadParameter("output must be table or json")

    print_analysis_table(console, result)


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
            print_fetch_result(console, result)
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
    print_fetch_result(console, result)


@app.command()
def draws(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, or all.")] = "all",
    limit: Annotated[
        int,
        typer.Option(
            "--limit",
            "-n",
            min=1,
            help="Number of recent draws to show per game.",
        ),
    ] = 5,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Show recent stored drawing numbers."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")

    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        games = _load_games(conn)
    else:
        metadata = db.get_game(conn, game)
        if metadata is None:
            raise typer.BadParameter(f"unknown game: {game}")
        games = (metadata,)

    draws_by_game = {
        metadata.slug: db.recent_draws(conn, metadata.slug, limit=limit)
        for metadata in games
    }
    if output == "json":
        console.print_json(json.dumps(draws_to_dict(games, draws_by_game, limit)))
        return

    print_draws_table(console, games, draws_by_game)


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
            format_probability(option.hit_rate),
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
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Recommend the highest hit-rate play style within a small budget."""
    conn = db.connect(ctx.obj["data_dir"])
    games = _load_games(conn)
    settings = AppSettings()
    generated_at = _generated_at()
    recommendations = recommend_highest_hit_rate(games, settings, budget)
    if not recommendations:
        raise typer.BadParameter("budget is below the cheapest supported wager")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")

    response_payload: dict[str, object] = {
        "generated_at": generated_at,
        "budget": budget,
        "best": recommendation_to_dict(recommendations[0]),
        "recommendations": [
            recommendation_to_dict(recommendation)
            for recommendation in recommendations
        ],
    }
    evaluation = None
    if evaluate == "openai":
        try:
            evaluation = evaluate_recommendations_with_openai(
                openai_recommendation_payload(
                    recommendations,
                    settings,
                    budget,
                    generated_at,
                ),
                model=openai_model,
            )
        except OpenAIEvaluationError as exc:
            raise typer.BadParameter(str(exc)) from exc
        response_payload["evaluation"] = evaluation

    if output == "json":
        console.print_json(json.dumps(response_payload))
        return

    print_recommendation_table(console, recommendations, budget, generated_at)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


def _generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@app.command("low-share")
def low_share(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, or all.")],
    count: Annotated[
        int,
        typer.Option(
            "--count",
            "-n",
            min=1,
            help="Number of low-share picks to generate per wager variation.",
        ),
    ] = 5,
    candidates: Annotated[
        int,
        typer.Option(
            "--candidates",
            min=1,
            help="Random candidates to score per wager variation.",
        ),
    ] = 1000,
    seed: Annotated[
        int | None,
        typer.Option("--seed", help="Seed for deterministic generation."),
    ] = None,
    avoid_recent_winning_combos: Annotated[
        bool,
        typer.Option(
            "--avoid-recent-winning-combos",
            help=(
                "Exclude exact winning combinations found in stored draw history. "
                "This does not improve draw odds."
            ),
        ),
    ] = False,
    last: Annotated[
        int | None,
        typer.Option(
            "--last",
            min=1,
            help="When avoiding recent winning combos, check only the most recent N draws.",
        ),
    ] = None,
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Generate valid picks that avoid common human number patterns."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    if candidates < count:
        raise typer.BadParameter("candidates must be greater than or equal to count")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        games = _load_games(conn)
    else:
        metadata = db.get_game(conn, game)
        if metadata is None:
            raise typer.BadParameter(f"unknown game: {game}")
        games = (metadata,)

    results = tuple(
        option_result
        for metadata in games
        for option_result in generate_low_share_options(
            conn,
            metadata,
            count=count,
            candidates=candidates,
            seed=seed,
            avoid_recent_winning_combos=avoid_recent_winning_combos,
            last=last,
        )
    )
    response_payload: dict[str, object] = {
        "count": count,
        "candidates": candidates,
        "avoid_recent_winning_combos": avoid_recent_winning_combos,
        "games": low_share_results_to_dict(results),
    }
    if seed is not None:
        response_payload["seed"] = seed
    evaluation = None
    if evaluate == "openai":
        try:
            evaluation = evaluate_low_share_with_openai(
                openai_low_share_payload(results),
                model=openai_model,
            )
        except OpenAIEvaluationError as exc:
            raise typer.BadParameter(str(exc)) from exc
        response_payload["evaluation"] = evaluation
    if output == "json":
        console.print_json(json.dumps(response_payload))
        return
    print_low_share_table(console, results)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


@audit_app.command("frequency")
def audit_frequency(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as cashpop.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Audit observed number frequencies against perfect uniform randomness."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = [
            result
            for slug in db.list_game_slugs(conn)
            for result in frequency_audit(conn, slug, last=last)
        ]
        evaluation = _evaluate_audits_if_requested(results, evaluate, openai_model)
        if output == "json":
            payload: dict[str, object] = {"audits": results}
            if evaluation is not None:
                payload["evaluation"] = evaluation
            console.print_json(json.dumps(payload))
            return
        print_audit_summary_table(console, results)
        if evaluation is not None:
            print_openai_evaluation(console, evaluation)
        return

    if db.get_game(conn, game) is None:
        raise typer.BadParameter(f"unknown game: {game}")
    results = frequency_audit(conn, game, last=last)
    evaluation = _evaluate_audits_if_requested(results, evaluate, openai_model)
    if output == "json":
        payload: dict[str, object]
        if len(results) == 1:
            payload = dict(results[0])
        else:
            payload = {"game_slug": game, "audits": results}
        if evaluation is not None:
            payload["evaluation"] = evaluation
        console.print_json(json.dumps(payload))
        return
    print_frequency_audit_tables(console, results)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


@audit_app.command("chi-square")
def audit_chi_square(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as powerball.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Run chi-square tests against perfect uniform randomness."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = [
            result
            for slug in db.list_game_slugs(conn)
            for result in chi_square_audit(conn, slug, last=last)
        ]
    else:
        if db.get_game(conn, game) is None:
            raise typer.BadParameter(f"unknown game: {game}")
        results = chi_square_audit(conn, game, last=last)
    evaluation = _evaluate_audits_if_requested(results, evaluate, openai_model)
    if output == "json":
        payload: dict[str, object] = {"audits": results}
        if evaluation is not None:
            payload["evaluation"] = evaluation
        console.print_json(json.dumps(payload))
        return
    print_audit_summary_table(console, results)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


@audit_app.command("all")
def audit_all(
    ctx: typer.Context,
    game: Annotated[
        str,
        typer.Argument(help="Game slug or 'all'."),
    ] = "all",
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    details: Annotated[
        bool,
        typer.Option("--details", help="Include full bucket and value details in JSON."),
    ] = False,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Run every randomness audit type across one game or all games."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        slugs = db.list_game_slugs(conn)
    else:
        if db.get_game(conn, game) is None:
            raise typer.BadParameter(f"unknown game: {game}")
        slugs = (game,)
    games = []
    summary_results = []
    for slug in slugs:
        audits = _all_audits_for_game(conn, slug, last)
        summary_results.extend(audits)
        games.append(
            {
                "game_slug": slug,
                "audits": audits if details else [compact_audit(audit) for audit in audits],
            }
        )
    evaluation = _evaluate_audits_if_requested(
        summary_results,
        evaluate,
        openai_model,
    )
    if output == "json":
        payload: dict[str, object] = {"games": games}
        if evaluation is not None:
            payload["evaluation"] = evaluation
        console.print_json(json.dumps(payload))
        return
    print_audit_summary_table(
        console,
        summary_results if details else [compact_audit(audit) for audit in summary_results]
    )
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


@audit_app.command("pairs")
def audit_pairs(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as hit-5.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Audit within-draw pair distributions."""
    _run_combination_command(
        ctx,
        game,
        output,
        last,
        evaluate,
        openai_model,
        size=2,
    )


@audit_app.command("triples")
def audit_triples(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as hit-5.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Audit within-draw triple distributions."""
    _run_combination_command(
        ctx,
        game,
        output,
        last,
        evaluate,
        openai_model,
        size=3,
    )


@audit_app.command("gaps")
def audit_gaps(
    ctx: typer.Context,
    game: Annotated[str, typer.Argument(help="Game slug, such as cashpop.")],
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output format: table or json."),
    ] = "table",
    last: Annotated[
        int | None,
        typer.Option("--last", min=1, help="Audit only the most recent N valid draws."),
    ] = None,
    evaluate: Annotated[
        str,
        typer.Option("--evaluate", help="Optional evaluator: none or openai."),
    ] = "none",
    openai_model: Annotated[
        str,
        typer.Option("--openai-model", help="OpenAI model used with --evaluate openai."),
    ] = DEFAULT_OPENAI_MODEL,
) -> None:
    """Audit draw intervals between number appearances."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = [
            result
            for slug in db.list_game_slugs(conn)
            for result in gap_audit(conn, slug, last=last)
        ]
    else:
        if db.get_game(conn, game) is None:
            raise typer.BadParameter(f"unknown game: {game}")
        results = gap_audit(conn, game, last=last)
    evaluation = _evaluate_audits_if_requested(results, evaluate, openai_model)
    if output == "json":
        if len(results) == 1:
            payload = dict(results[0])
        else:
            payload = {"audits": results}
        if evaluation is not None:
            payload["evaluation"] = evaluation
        console.print_json(json.dumps(payload))
        return
    print_gap_audit_tables(console, results)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


def _run_combination_command(
    ctx: typer.Context,
    game: str,
    output: str,
    last: int | None,
    evaluate: str,
    openai_model: str,
    *,
    size: int,
) -> None:
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = [
            result
            for slug in db.list_game_slugs(conn)
            for result in combination_audit(conn, slug, size=size, last=last)
        ]
    else:
        if db.get_game(conn, game) is None:
            raise typer.BadParameter(f"unknown game: {game}")
        results = combination_audit(conn, game, size=size, last=last)
    evaluation = _evaluate_audits_if_requested(results, evaluate, openai_model)
    if output == "json":
        if len(results) == 1:
            payload = dict(results[0])
        else:
            payload = {"audits": results}
        if evaluation is not None:
            payload["evaluation"] = evaluation
        console.print_json(json.dumps(payload))
        return
    print_combination_audit_tables(console, results)
    if evaluation is not None:
        print_openai_evaluation(console, evaluation)


def _all_audits_for_game(
    conn,
    slug: str,
    last: int | None,
) -> list[dict[str, object]]:
    return [
        *frequency_audit(conn, slug, last=last),
        *chi_square_audit(conn, slug, last=last),
        *combination_audit(conn, slug, size=2, last=last),
        *combination_audit(conn, slug, size=3, last=last),
        *gap_audit(conn, slug, last=last),
    ]


def _evaluate_audits_if_requested(
    audits: list[dict[str, object]],
    evaluate: str,
    openai_model: str,
) -> dict[str, object] | None:
    if evaluate == "none":
        return None
    try:
        return explain_audits_with_openai(
            openai_audit_payload(audits),
            model=openai_model,
        )
    except OpenAIEvaluationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _load_games(conn) -> tuple[GameMetadata, ...]:
    games = []
    for slug in db.list_game_slugs(conn):
        metadata = db.get_game(conn, slug)
        if metadata is not None:
            games.append(metadata)
    return tuple(games)


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
