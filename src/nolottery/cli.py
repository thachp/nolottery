from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import db
from .audit import chi_square_audit, combination_audit, frequency_audit, gap_audit
from .ev import AnalysisResult, analyze_game
from .fetch import FetchResult, fetch_game, fetch_game_backfill
from .ledger import LedgerEntry
from .ledger import add_entry as add_ledger_entry
from .ledger import summarize as summarize_ledger
from .low_share import LowShareOptionResult, generate_low_share_options
from .metadata import GameMetadata
from .openai_eval import DEFAULT_OPENAI_MODEL
from .openai_eval import OpenAIEvaluationError
from .openai_eval import evaluate_low_share_with_openai
from .openai_eval import evaluate_recommendations_with_openai
from .openai_eval import explain_audits_with_openai
from .recommend import Recommendation, displayed_hit_rate, recommend_highest_hit_rate
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
    recommendations = recommend_highest_hit_rate(games, settings, budget)
    if not recommendations:
        raise typer.BadParameter("budget is below the cheapest supported wager")
    if evaluate not in {"none", "openai"}:
        raise typer.BadParameter("evaluate must be none or openai")
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")

    response_payload: dict[str, object] = {
        "budget": budget,
        "best": _recommendation_to_dict(recommendations[0]),
        "recommendations": [
            _recommendation_to_dict(recommendation)
            for recommendation in recommendations
        ],
    }
    evaluation = None
    if evaluate == "openai":
        try:
            evaluation = evaluate_recommendations_with_openai(
                _openai_recommendation_payload(recommendations, settings, budget),
                model=openai_model,
            )
        except OpenAIEvaluationError as exc:
            raise typer.BadParameter(str(exc)) from exc
        response_payload["evaluation"] = evaluation

    if output == "json":
        console.print_json(json.dumps(response_payload))
        return

    _print_recommendation_table(recommendations, budget)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
        "games": _low_share_results_to_dict(results),
    }
    if seed is not None:
        response_payload["seed"] = seed
    evaluation = None
    if evaluate == "openai":
        try:
            evaluation = evaluate_low_share_with_openai(
                _openai_low_share_payload(results),
                model=openai_model,
            )
        except OpenAIEvaluationError as exc:
            raise typer.BadParameter(str(exc)) from exc
        response_payload["evaluation"] = evaluation
    if output == "json":
        console.print_json(json.dumps(response_payload))
        return
    _print_low_share_table(results)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
        _print_audit_summary_table(results)
        if evaluation is not None:
            _print_openai_evaluation(evaluation)
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
    _print_frequency_audit_tables(results)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
    _print_audit_summary_table(results)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
                "audits": audits if details else [_compact_audit(audit) for audit in audits],
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
    _print_audit_summary_table(
        summary_results if details else [_compact_audit(audit) for audit in summary_results]
    )
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
    _print_gap_audit_tables(results)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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
    _print_combination_audit_tables(results)
    if evaluation is not None:
        _print_openai_evaluation(evaluation)


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


def _compact_audit(audit: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in audit.items()
        if key not in {"buckets", "values", "gap_buckets"}
    }


def _evaluate_audits_if_requested(
    audits: list[dict[str, object]],
    evaluate: str,
    openai_model: str,
) -> dict[str, object] | None:
    if evaluate == "none":
        return None
    try:
        return explain_audits_with_openai(
            _openai_audit_payload(audits),
            model=openai_model,
        )
    except OpenAIEvaluationError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _openai_audit_payload(audits: list[dict[str, object]]) -> dict[str, object]:
    if not audits:
        raise OpenAIEvaluationError("no audit results were available to explain")
    warn_count = _count_status(audits, "WARN")
    insufficient_count = _count_status(audits, "INSUFFICIENT_DATA")
    not_applicable_count = _count_status(audits, "NOT_APPLICABLE")
    max_draw_count = max(int(audit.get("draw_count", 0)) for audit in audits)
    return {
        "objective": (
            "Explain lottery randomness audit results in plain language. "
            "The explanation must not claim that historical results predict future draws."
        ),
        "facts": {
            "audit_count": len(audits),
            "warn_count": warn_count,
            "insufficient_data_count": insufficient_count,
            "not_applicable_count": not_applicable_count,
            "max_draw_count": max_draw_count,
        },
        "constraints": [
            "Do not change p-values, statuses, draw counts, expected counts, or warnings.",
            "WARN means a screening signal worth reviewing, not proof of drawing bias.",
            "INSUFFICIENT_DATA means the test is too sparse for reliable inference.",
            "Historical audit results do not identify winning future numbers.",
        ],
        "audits": [_openai_audit_to_dict(audit) for audit in audits],
    }


def _openai_audit_to_dict(audit: dict[str, object]) -> dict[str, object]:
    payload = _compact_audit(audit)
    if "buckets" in audit:
        payload["notable_buckets"] = _notable_buckets(audit["buckets"])
    if "values" in audit:
        payload["notable_values"] = _notable_values(audit["values"])
    if "gap_buckets" in audit:
        payload["notable_gap_buckets"] = _notable_gap_buckets(
            audit["gap_buckets"]
        )
    return payload


def _count_status(audits: list[dict[str, object]], status: str) -> int:
    return sum(1 for audit in audits if audit.get("status") == status)


def _notable_buckets(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    buckets = [bucket for bucket in value if isinstance(bucket, dict)]
    sortable = [
        (
            abs(float(bucket.get("delta", 0))),
            int(bucket.get("observed", 0)),
            bucket,
        )
        for bucket in buckets
    ]
    sorted_buckets = sorted(
        sortable,
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )
    return [_compact_bucket(bucket) for _, _, bucket in sorted_buckets[:5]]


def _notable_values(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    values = [item for item in value if isinstance(item, dict)]
    sortable = [
        (
            int(item.get("current_gap", 0)),
            int(item.get("appearances", 0)),
            item,
        )
        for item in values
    ]
    sorted_values = sorted(
        sortable,
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )
    return [_compact_gap_value(item) for _, _, item in sorted_values[:5]]


def _notable_gap_buckets(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    buckets = [bucket for bucket in value if isinstance(bucket, dict)]
    sortable = [
        (
            abs(float(bucket.get("observed", 0)) - float(bucket.get("expected", 0))),
            bucket,
        )
        for bucket in buckets
    ]
    return [
        _compact_bucket(bucket)
        for _, bucket in sorted(sortable, key=lambda item: item[0], reverse=True)[:5]
    ]


def _compact_bucket(bucket: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in bucket.items()
        if key in {"value", "combination", "gap", "observed", "expected", "delta", "ratio"}
    }


def _compact_gap_value(value: dict[str, object]) -> dict[str, object]:
    return {
        key: item
        for key, item in value.items()
        if key in {"value", "appearances", "current_gap", "max_gap", "average_gap"}
    }


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


def _print_low_share_table(results: tuple[LowShareOptionResult, ...]) -> None:
    table = Table()
    table.add_column("Game", no_wrap=True)
    table.add_column("Wager")
    table.add_column("Pick")
    table.add_column("Low-Share Score", justify="right")
    table.add_column("Reasons")
    for result in results:
        for pick in result.picks:
            table.add_row(
                result.game_name,
                result.option_label,
                pick.label,
                str(pick.low_share_score),
                "; ".join(pick.reasons[:2]),
            )
    console.print(table)
    console.print(
        "Low-share picks do not improve draw odds; they only aim to reduce "
        "common-player-pattern overlap."
    )
    for warning in _low_share_warnings(results):
        console.print(f"Warning: {warning}")


def _print_openai_evaluation(evaluation: dict[str, object]) -> None:
    if "summary" in evaluation:
        console.print(f"OpenAI summary: {evaluation['summary']}")
        console.print(f"Overall status: {evaluation['overall_status']}")
        for finding in evaluation.get("notable_findings", []):
            console.print(f"Finding: {finding}")
        for limitation in evaluation.get("limitations", []):
            console.print(f"Limitation: {limitation}")
        for step in evaluation.get("recommended_next_steps", []):
            console.print(f"Next step: {step}")
        return
    console.print(f"OpenAI decision: {evaluation['decision']}")
    selected_candidate = evaluation.get("selected_candidate_id")
    if selected_candidate is not None:
        console.print(f"Selected candidate: {selected_candidate}")
    console.print(f"Confidence: {evaluation['confidence']}")
    console.print(f"Rationale: {evaluation['rationale']}")


def _print_frequency_audit_tables(results: list[dict[str, object]]) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} frequency: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"p-value: {_format_optional_float(result['p_value'])}")
        for warning in result["warnings"]:
            console.print(f"Warning: {warning}")
        table = Table()
        table.add_column("Value", justify="right")
        table.add_column("Observed", justify="right")
        table.add_column("Expected", justify="right")
        table.add_column("Delta", justify="right")
        for bucket in result["buckets"]:
            table.add_row(
                str(bucket["value"]),
                str(bucket["observed"]),
                f"{bucket['expected']:.2f}",
                f"{bucket['delta']:.2f}",
            )
        console.print(table)


def _print_audit_summary_table(results: list[dict[str, object]]) -> None:
    table = Table()
    table.add_column("Game", no_wrap=True)
    table.add_column("Pool", no_wrap=True)
    table.add_column("Test", no_wrap=True)
    table.add_column("Draws", justify="right")
    table.add_column("Status", no_wrap=True)
    table.add_column("p-value", justify="right")
    table.add_column("Expected", justify="right")
    for result in results:
        table.add_row(
            str(result["game_slug"]),
            str(result["pool"]),
            str(result["test"]),
            str(result["draw_count"]),
            str(result["status"]),
            _format_optional_float(result.get("p_value")),
            _format_optional_count(result.get("expected_per_bucket")),
        )
    console.print(table)
    console.print(
        "Statistical warnings are screening signals, not proof of non-random drawing behavior."
    )


def _print_combination_audit_tables(results: list[dict[str, object]]) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} {result['test']}: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"p-value: {_format_optional_float(result['p_value'])}")
        for warning in result["warnings"]:
            console.print(f"Warning: {warning}")
        table = Table()
        table.add_column("Combination")
        table.add_column("Observed", justify="right")
        table.add_column("Expected", justify="right")
        top_buckets = sorted(
            result["buckets"],
            key=lambda bucket: bucket["observed"],
            reverse=True,
        )[:20]
        for bucket in top_buckets:
            combination = bucket["combination"]
            label = (
                ", ".join(str(value) for value in combination)
                if isinstance(combination, list)
                else str(combination)
            )
            table.add_row(
                label,
                str(bucket["observed"]),
                f"{bucket['expected']:.2f}",
            )
        console.print(table)


def _print_gap_audit_tables(results: list[dict[str, object]]) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} gaps: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"Completed gaps: {result['completed_gap_count']}")
        console.print(f"p-value: {_format_optional_float(result['p_value'])}")
        for warning in result["warnings"]:
            console.print(f"Warning: {warning}")
        table = Table()
        table.add_column("Value", justify="right")
        table.add_column("Appearances", justify="right")
        table.add_column("Current Gap", justify="right")
        table.add_column("Max Gap", justify="right")
        table.add_column("Average Gap", justify="right")
        for value in result["values"]:
            table.add_row(
                str(value["value"]),
                str(value["appearances"]),
                str(value["current_gap"]),
                str(value["max_gap"] if value["max_gap"] is not None else "n/a"),
                (
                    f"{value['average_gap']:.2f}"
                    if value["average_gap"] is not None
                    else "n/a"
                ),
            )
        console.print(table)


def _format_optional_float(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.6g}"


def _format_optional_count(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"


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


def _low_share_results_to_dict(
    results: tuple[LowShareOptionResult, ...],
) -> list[dict[str, object]]:
    games: dict[str, dict[str, object]] = {}
    for result in results:
        game_payload = games.setdefault(
            result.game_slug,
            {
                "game_slug": result.game_slug,
                "game": result.game_name,
                "options": [],
                "warnings": [],
            },
        )
        game_payload["options"].append(
            {
                "option_slug": result.option_slug,
                "option": result.option_label,
                "picks": [
                    {
                        "numbers": list(pick.numbers),
                        "label": pick.label,
                        "low_share_score": pick.low_share_score,
                        "reasons": list(pick.reasons),
                        "method": pick.method,
                    }
                    for pick in result.picks
                ],
                "warnings": list(result.warnings),
            }
        )
        game_payload["warnings"] = list(
            dict.fromkeys([*game_payload["warnings"], *result.warnings])
        )
    return list(games.values())


def _low_share_warnings(results: tuple[LowShareOptionResult, ...]) -> tuple[str, ...]:
    warnings = [
        f"{result.game_name} / {result.option_label}: {warning}"
        for result in results
        for warning in result.warnings
    ]
    return tuple(dict.fromkeys(warnings))


def _openai_low_share_payload(
    results: tuple[LowShareOptionResult, ...],
) -> dict[str, object]:
    candidates = [
        {
            "candidate_id": _low_share_candidate_id(result, index),
            "game_slug": result.game_slug,
            "game": result.game_name,
            "option_slug": result.option_slug,
            "option": result.option_label,
            "numbers": list(pick.numbers),
            "label": pick.label,
            "low_share_score": pick.low_share_score,
            "reasons": list(pick.reasons),
            "method": pick.method,
        }
        for result in results
        for index, pick in enumerate(result.picks, start=1)
    ]
    if not candidates:
        raise OpenAIEvaluationError("no low-share candidates were available to evaluate")
    best_candidate = max(
        candidates,
        key=lambda candidate: candidate["low_share_score"],
    )
    return {
        "objective": (
            "Select one generated low-share candidate for entertainment, or SKIP. "
            "Low-share scores estimate avoidance of common human number patterns, "
            "not likelihood of being drawn."
        ),
        "facts": {
            "candidate_count": len(candidates),
            "best_candidate_id": best_candidate["candidate_id"],
            "best_low_share_score": best_candidate["low_share_score"],
            "no_odds_edge": True,
        },
        "best_low_share_candidate": best_candidate,
        "constraints": [
            "Do not claim any candidate has better draw odds.",
            "Treat low_share_score as a heuristic anti-popularity score, not a probability.",
            "A selected candidate is only an entertainment choice intended to reduce overlap with common player patterns.",
            "SKIP is valid because every fair lottery ticket remains negative expected value unless EV analysis says otherwise.",
        ],
        "candidates": candidates,
    }


def _low_share_candidate_id(result: LowShareOptionResult, index: int) -> str:
    return f"{result.game_slug}:{result.option_slug}:{index}"


def _openai_recommendation_payload(
    recommendations: tuple[Recommendation, ...],
    settings: AppSettings,
    budget: float,
) -> dict[str, object]:
    candidates = [
        _openai_candidate_to_dict(recommendation)
        for recommendation in recommendations
    ]
    best_hit_rate = candidates[0]
    best_ev = max(candidates, key=lambda candidate: candidate["net_after_tax_ev"])
    required_edge = best_ev["ticket_cost"] * settings.bankroll.min_edge_percent
    deterministic_decision = (
        "PLAY" if best_ev["net_after_tax_ev"] > required_edge else "SKIP"
    )
    deterministic_reason = (
        "at least one affordable option has positive net after-tax expected value"
        if deterministic_decision == "PLAY"
        else "all affordable options have non-positive net after-tax expected value"
    )
    return {
        "budget": budget,
        "objective": (
            "Make the optimal decision for the budget. SKIP is allowed. "
            "A play recommendation can be overridden subjectively only as entertainment."
        ),
        "deterministic_decision": deterministic_decision,
        "deterministic_reason": deterministic_reason,
        "best_hit_rate_option": best_hit_rate,
        "best_ev_option": best_ev,
        "constraints": [
            "Do not change candidate costs, hit rates, or expected values.",
            "If all net expected values are negative, SKIP is the mathematically optimal decision.",
            "PLAY_FOR_ENTERTAINMENT is allowed only when the rationale clearly accepts expected loss.",
            "Quick-pick numbers are intentionally omitted because they have no odds advantage.",
        ],
        "candidates": candidates,
    }


def _openai_candidate_to_dict(recommendation: Recommendation) -> dict[str, object]:
    option = recommendation.option
    return {
        "candidate_slug": f"{recommendation.game_slug}:{option.option_slug}",
        "game_slug": recommendation.game_slug,
        "game": recommendation.game_name,
        "option_slug": option.option_slug,
        "option": option.option_label,
        "ticket_cost": option.ticket_cost,
        "hit_rate": displayed_hit_rate(recommendation),
        "net_after_tax_ev": option.net_after_tax_ev,
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
