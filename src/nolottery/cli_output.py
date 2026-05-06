from __future__ import annotations

from rich.console import Console
from rich.table import Table

from . import db
from .ev import AnalysisResult
from .fetch import FetchResult
from .low_share import LowShareOptionResult
from .metadata import GameMetadata
from .recommend import Recommendation, displayed_hit_rate


def print_fetch_result(console: Console, result: FetchResult) -> None:
    console.print(
        f"{result.game_name}: fetched {result.draw_count} draw"
        f"{'' if result.draw_count == 1 else 's'} and "
        f"{result.prize_row_count} prize rows"
        f" from {result.page_count} page"
        f"{'' if result.page_count == 1 else 's'}"
    )


def print_analysis_table(console: Console, result: AnalysisResult) -> None:
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
            format_probability(option.hit_rate),
            str(option.max_recommended_tickets if result.decision == "PLAY" else 0),
        )
    console.print(table)


def print_recommendation_table(
    console: Console,
    recommendations: tuple[Recommendation, ...],
    budget: float,
    generated_at: str,
) -> None:
    console.print(f"Generated at: {generated_at}")
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
            format_probability(displayed_hit_rate(recommendation)),
            f"${option.net_after_tax_ev:.2f}",
            recommendation.prediction_label,
        )
    console.print(table)
    console.print(f"Recommended: {recommendations[0].reason}")
    console.print("Prediction method: quick-pick random; no odds advantage.")


def print_low_share_table(
    console: Console,
    results: tuple[LowShareOptionResult, ...],
) -> None:
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
    for warning in low_share_warnings(results):
        console.print(f"Warning: {warning}")


def print_draws_table(
    console: Console,
    games: tuple[GameMetadata, ...],
    draws_by_game: dict[str, tuple[db.StoredDraw, ...]],
) -> None:
    table = Table()
    table.add_column("Game", no_wrap=True)
    table.add_column("Draw Date", no_wrap=True)
    table.add_column("Winning Numbers")
    for metadata in games:
        draws = draws_by_game[metadata.slug]
        if not draws:
            table.add_row(metadata.name, "No stored draws", "")
            continue
        for draw in draws:
            table.add_row(draw.game_name, draw.draw_date, draw.winning_number)
    console.print(table)
    if not any(draws_by_game.values()):
        console.print("No stored draw data. Run `lottery fetch all` first.")


def print_openai_evaluation(console: Console, evaluation: dict[str, object]) -> None:
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


def print_frequency_audit_tables(
    console: Console,
    results: list[dict[str, object]],
) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} frequency: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"p-value: {format_optional_float(result['p_value'])}")
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


def print_audit_summary_table(
    console: Console,
    results: list[dict[str, object]],
) -> None:
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
            format_optional_float(result.get("p_value")),
            format_optional_count(result.get("expected_per_bucket")),
        )
    console.print(table)
    console.print(
        "Statistical warnings are screening signals, not proof of non-random drawing behavior."
    )


def print_combination_audit_tables(
    console: Console,
    results: list[dict[str, object]],
) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} {result['test']}: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"p-value: {format_optional_float(result['p_value'])}")
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


def print_gap_audit_tables(
    console: Console,
    results: list[dict[str, object]],
) -> None:
    for result in results:
        console.print(
            f"{result['game_slug']} / {result['pool']} gaps: "
            f"{result['status']}"
        )
        console.print(f"Draws: {result['draw_count']}")
        console.print(f"Completed gaps: {result['completed_gap_count']}")
        console.print(f"p-value: {format_optional_float(result['p_value'])}")
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


def low_share_warnings(
    results: tuple[LowShareOptionResult, ...],
) -> tuple[str, ...]:
    warnings = [
        f"{result.game_name} / {result.option_label}: {warning}"
        for result in results
        for warning in result.warnings
    ]
    return tuple(dict.fromkeys(warnings))


def format_probability(probability: float) -> str:
    if probability <= 0:
        return "n/a"
    return f"1:{1 / probability:.2f}"


def format_optional_float(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.6g}"


def format_optional_count(value: object) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2f}"
