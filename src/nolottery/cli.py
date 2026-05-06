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
from .metadata import GameMetadata
from .openai_eval import DEFAULT_OPENAI_MODEL
from .openai_eval import OpenAIEvaluationError
from .openai_eval import evaluate_recommendations_with_openai
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
) -> None:
    """Audit observed number frequencies against perfect uniform randomness."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
    conn = db.connect(ctx.obj["data_dir"])
    if game == "all":
        results = [
            result
            for slug in db.list_game_slugs(conn)
            for result in frequency_audit(conn, slug, last=last)
        ]
        if output == "json":
            console.print_json(json.dumps({"audits": results}))
            return
        _print_audit_summary_table(results)
        return

    if db.get_game(conn, game) is None:
        raise typer.BadParameter(f"unknown game: {game}")
    results = frequency_audit(conn, game, last=last)
    if output == "json":
        payload: dict[str, object]
        if len(results) == 1:
            payload = results[0]
        else:
            payload = {"game_slug": game, "audits": results}
        console.print_json(json.dumps(payload))
        return
    _print_frequency_audit_tables(results)


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
) -> None:
    """Run chi-square tests against perfect uniform randomness."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
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
    if output == "json":
        console.print_json(json.dumps({"audits": results}))
        return
    _print_audit_summary_table(results)


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
) -> None:
    """Run every randomness audit type across one game or all games."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
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
    if output == "json":
        console.print_json(json.dumps({"games": games}))
        return
    _print_audit_summary_table(
        summary_results if details else [_compact_audit(audit) for audit in summary_results]
    )


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
) -> None:
    """Audit within-draw pair distributions."""
    _run_combination_command(ctx, game, output, last, size=2)


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
) -> None:
    """Audit within-draw triple distributions."""
    _run_combination_command(ctx, game, output, last, size=3)


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
) -> None:
    """Audit draw intervals between number appearances."""
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
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
    if output == "json":
        if len(results) == 1:
            console.print_json(json.dumps(results[0]))
        else:
            console.print_json(json.dumps({"audits": results}))
        return
    _print_gap_audit_tables(results)


def _run_combination_command(
    ctx: typer.Context,
    game: str,
    output: str,
    last: int | None,
    *,
    size: int,
) -> None:
    if output not in {"table", "json"}:
        raise typer.BadParameter("output must be table or json")
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
    if output == "json":
        if len(results) == 1:
            console.print_json(json.dumps(results[0]))
        else:
            console.print_json(json.dumps({"audits": results}))
        return
    _print_combination_audit_tables(results)


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


def _print_openai_evaluation(evaluation: dict[str, object]) -> None:
    console.print(f"OpenAI decision: {evaluation['decision']}")
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
