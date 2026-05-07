from __future__ import annotations

from . import db
from .ev import AnalysisResult
from .low_share import LowShareOptionResult
from .metadata import GameMetadata
from .openai_eval import OpenAIEvaluationError
from .recommend import Recommendation, displayed_hit_rate
from .settings import AppSettings


def analysis_to_dict(
    result: AnalysisResult,
    *,
    jurisdiction_code: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {}
    if jurisdiction_code is not None:
        payload["jurisdiction_code"] = jurisdiction_code
    payload.update(
        {
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
    )
    return payload

def recommendation_to_dict(recommendation: Recommendation) -> dict[str, object]:
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


def low_share_results_to_dict(
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


def draws_to_dict(
    games: tuple[GameMetadata, ...],
    draws_by_game: dict[str, tuple[db.StoredDraw, ...]],
    limit: int,
    *,
    jurisdiction_code: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "limit": limit,
        "games": [
            {
                **(
                    {"jurisdiction_code": jurisdiction_code}
                    if jurisdiction_code is not None
                    else {}
                ),
                "game_slug": metadata.slug,
                "game": metadata.name,
                "draws": [
                    {
                        **(
                            {"jurisdiction_code": draw.jurisdiction_code}
                            if jurisdiction_code is not None
                            else {}
                        ),
                        "draw_date": draw.draw_date,
                        "winning_number": draw.winning_number,
                    }
                    for draw in draws_by_game[metadata.slug]
                ],
            }
            for metadata in games
        ],
    }
    if jurisdiction_code is not None:
        payload["jurisdiction_code"] = jurisdiction_code
    return payload


def compact_audit(audit: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in audit.items()
        if key not in {"buckets", "values", "gap_buckets"}
    }


def openai_audit_payload(audits: list[dict[str, object]]) -> dict[str, object]:
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


def openai_low_share_payload(
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


def openai_recommendation_payload(
    recommendations: tuple[Recommendation, ...],
    settings: AppSettings,
    budget: float,
    generated_at: str,
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
        "generated_at": generated_at,
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


def _openai_audit_to_dict(audit: dict[str, object]) -> dict[str, object]:
    payload = compact_audit(audit)
    if "buckets" in audit:
        payload["notable_buckets"] = _notable_buckets(audit["buckets"])
    if "values" in audit:
        payload["notable_values"] = _notable_values(audit["values"])
    if "gap_buckets" in audit:
        payload["notable_gap_buckets"] = _notable_gap_buckets(audit["gap_buckets"])
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


def _low_share_candidate_id(result: LowShareOptionResult, index: int) -> str:
    return f"{result.game_slug}:{result.option_slug}:{index}"


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
