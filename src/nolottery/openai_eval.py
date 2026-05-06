from __future__ import annotations

import json
import os
from typing import Any

import httpx


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-5.2"


class OpenAIEvaluationError(RuntimeError):
    """Raised when OpenAI cannot return a usable lottery decision."""


DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["SKIP", "PLAY", "PLAY_FOR_ENTERTAINMENT"],
        },
        "selected_option_slug": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "rationale": {"type": "string"},
        "tradeoffs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "facts_used": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "budget": {"type": "number"},
                "deterministic_decision": {"type": "string"},
                "best_hit_rate_option": {"type": "string"},
                "best_hit_rate": {"type": "number"},
                "best_net_after_tax_ev": {"type": "number"},
            },
            "required": [
                "budget",
                "deterministic_decision",
                "best_hit_rate_option",
                "best_hit_rate",
                "best_net_after_tax_ev",
            ],
        },
    },
    "required": [
        "decision",
        "selected_option_slug",
        "confidence",
        "rationale",
        "tradeoffs",
        "facts_used",
    ],
}


LOW_SHARE_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["SKIP", "PLAY_FOR_ENTERTAINMENT"],
        },
        "selected_candidate_id": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        },
        "selected_game_slug": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        },
        "selected_option_slug": {
            "anyOf": [{"type": "string"}, {"type": "null"}],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
        "rationale": {"type": "string"},
        "tradeoffs": {
            "type": "array",
            "items": {"type": "string"},
        },
        "facts_used": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "candidate_count": {"type": "integer"},
                "best_candidate_id": {"type": "string"},
                "best_low_share_score": {"type": "number"},
                "no_odds_edge": {"type": "boolean"},
            },
            "required": [
                "candidate_count",
                "best_candidate_id",
                "best_low_share_score",
                "no_odds_edge",
            ],
        },
    },
    "required": [
        "decision",
        "selected_candidate_id",
        "selected_game_slug",
        "selected_option_slug",
        "confidence",
        "rationale",
        "tradeoffs",
        "facts_used",
    ],
}


AUDIT_EXPLANATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "overall_status": {
            "type": "string",
            "enum": ["OK", "WARN", "INSUFFICIENT_DATA", "MIXED", "NOT_APPLICABLE"],
        },
        "notable_findings": {
            "type": "array",
            "items": {"type": "string"},
        },
        "limitations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "recommended_next_steps": {
            "type": "array",
            "items": {"type": "string"},
        },
        "facts_used": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "audit_count": {"type": "integer"},
                "warn_count": {"type": "integer"},
                "insufficient_data_count": {"type": "integer"},
                "not_applicable_count": {"type": "integer"},
                "max_draw_count": {"type": "integer"},
            },
            "required": [
                "audit_count",
                "warn_count",
                "insufficient_data_count",
                "not_applicable_count",
                "max_draw_count",
            ],
        },
    },
    "required": [
        "summary",
        "overall_status",
        "notable_findings",
        "limitations",
        "recommended_next_steps",
        "facts_used",
    ],
}


def evaluate_recommendations_with_openai(
    payload: dict[str, Any],
    model: str = DEFAULT_OPENAI_MODEL,
) -> dict[str, Any]:
    evaluation = _evaluate_with_openai(
        payload,
        model=model,
        schema_name="lottery_decision",
        schema=DECISION_SCHEMA,
        system_prompt=(
            "You evaluate lottery recommendations. Return only strict JSON "
            "matching the provided schema. Treat all numeric odds, costs, "
            "expected values, and candidate identifiers as immutable facts. "
            "You may choose SKIP when the math is unfavorable. You may choose "
            "PLAY_FOR_ENTERTAINMENT only when the tradeoff is explicitly framed "
            "as entertainment despite negative expected value."
        ),
    )
    _validate_evaluation(evaluation)
    return evaluation


def explain_audits_with_openai(
    payload: dict[str, Any],
    model: str = DEFAULT_OPENAI_MODEL,
) -> dict[str, Any]:
    evaluation = _evaluate_with_openai(
        payload,
        model=model,
        schema_name="lottery_audit_explanation",
        schema=AUDIT_EXPLANATION_SCHEMA,
        system_prompt=(
            "You explain lottery randomness audit results. Return only strict JSON "
            "matching the provided schema. Treat statuses, draw counts, p-values, "
            "expected counts, warnings, and audit identifiers as immutable facts. "
            "Do not claim that historical audit results predict future winning "
            "numbers. Explain WARN as a screening signal, not proof of bias, and "
            "explain INSUFFICIENT_DATA as too sparse for reliable inference."
        ),
    )
    _validate_audit_explanation(evaluation)
    return evaluation


def evaluate_low_share_with_openai(
    payload: dict[str, Any],
    model: str = DEFAULT_OPENAI_MODEL,
) -> dict[str, Any]:
    evaluation = _evaluate_with_openai(
        payload,
        model=model,
        schema_name="low_share_lottery_decision",
        schema=LOW_SHARE_DECISION_SCHEMA,
        system_prompt=(
            "You evaluate low-share lottery number candidates. Return only strict "
            "JSON matching the provided schema. Treat candidate identifiers, "
            "numbers, low-share scores, and reasons as immutable facts. You must "
            "not claim any candidate has better draw odds. You may select one "
            "candidate only as an entertainment choice that aims to reduce common "
            "player-pattern overlap, or choose SKIP."
        ),
    )
    _validate_low_share_evaluation(evaluation)
    return evaluation


def _evaluate_with_openai(
    payload: dict[str, Any],
    *,
    model: str,
    schema_name: str,
    schema: dict[str, Any],
    system_prompt: str,
) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIEvaluationError(
            "OPENAI_API_KEY is required when --evaluate openai is used"
        )

    request_body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "strict": True,
                "schema": schema,
            }
        },
    }

    try:
        response = httpx.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_body,
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise OpenAIEvaluationError(f"OpenAI evaluation failed: {exc}") from exc

    output_text = _extract_output_text(response.json())
    try:
        evaluation = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIEvaluationError("OpenAI returned invalid JSON") from exc

    return evaluation


def _extract_output_text(response_payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for output in response_payload.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text" and "text" in content:
                chunks.append(content["text"])
            if content.get("type") == "refusal":
                raise OpenAIEvaluationError("OpenAI refused to evaluate the payload")
    if not chunks:
        raise OpenAIEvaluationError("OpenAI response did not include output text")
    return "".join(chunks)


def _validate_evaluation(evaluation: Any) -> None:
    if not isinstance(evaluation, dict):
        raise OpenAIEvaluationError("OpenAI evaluation must be a JSON object")
    if evaluation.get("decision") not in {
        "SKIP",
        "PLAY",
        "PLAY_FOR_ENTERTAINMENT",
    }:
        raise OpenAIEvaluationError("OpenAI evaluation has an invalid decision")
    if evaluation.get("confidence") not in {"low", "medium", "high"}:
        raise OpenAIEvaluationError("OpenAI evaluation has an invalid confidence")


def _validate_low_share_evaluation(evaluation: Any) -> None:
    if not isinstance(evaluation, dict):
        raise OpenAIEvaluationError("OpenAI evaluation must be a JSON object")
    if evaluation.get("decision") not in {"SKIP", "PLAY_FOR_ENTERTAINMENT"}:
        raise OpenAIEvaluationError("OpenAI evaluation has an invalid decision")
    if evaluation.get("confidence") not in {"low", "medium", "high"}:
        raise OpenAIEvaluationError("OpenAI evaluation has an invalid confidence")


def _validate_audit_explanation(evaluation: Any) -> None:
    if not isinstance(evaluation, dict):
        raise OpenAIEvaluationError("OpenAI evaluation must be a JSON object")
    if evaluation.get("overall_status") not in {
        "OK",
        "WARN",
        "INSUFFICIENT_DATA",
        "MIXED",
        "NOT_APPLICABLE",
    }:
        raise OpenAIEvaluationError("OpenAI audit explanation has an invalid status")
