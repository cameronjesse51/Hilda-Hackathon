"""Helpers for translating tool results into client-facing stream events."""

from __future__ import annotations

import json


def college_results_event(tool_name: str, tool_output: str) -> dict | None:
    """Return a validated-enough college_results payload for SSE emission.

    Full contract validation belongs at the normalization boundary. This guard
    prevents tool errors or unrelated JSON from being presented as college
    cards if a handler changes or fails unexpectedly.
    """
    if tool_name != "search_colleges":
        return None

    try:
        payload = json.loads(tool_output)
    except (TypeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("event") != "college_results":
        return None
    if payload.get("schema_version") != "2.0":
        return None
    if not isinstance(payload.get("colleges"), list):
        return None
    if not isinstance(payload.get("query"), dict):
        return None
    if not payload.get("recommendation_set_id") or not payload.get("generated_at"):
        return None

    return payload
