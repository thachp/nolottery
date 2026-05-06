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


def evaluate_recommendations_with_openai(
    payload: dict[str, Any],
    model: str = DEFAULT_OPENAI_MODEL,
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
                "content": (
                    "You evaluate lottery recommendations. Return only strict JSON "
                    "matching the provided schema. Treat all numeric odds, costs, "
                    "expected values, and candidate identifiers as immutable facts. "
                    "You may choose SKIP when the math is unfavorable. You may choose "
                    "PLAY_FOR_ENTERTAINMENT only when the tradeoff is explicitly framed "
                    "as entertainment despite negative expected value."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "lottery_decision",
                "strict": True,
                "schema": DECISION_SCHEMA,
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

    _validate_evaluation(evaluation)
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
