"""Normalize college-search rows into the public recommendation contract.

This module is deliberately independent of Supabase and the LLM clients so the
data boundary can be tested without network credentials.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "1.0"
EVENT_NAME = "college_results"
DEFAULT_SOURCE_NAME = "U.S. Department of Education College Scorecard"
HIGHLY_SELECTIVE_RATE = 0.20
REACH_RATE = 0.35
LIKELY_RATE = 0.70
GPA_MARGIN = 0.15


def _first(row: dict, *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _number(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value if value >= 0 else None
    try:
        parsed = float(str(value).replace("$", "").replace(",", "").strip())
        if parsed < 0:
            return None
        return int(parsed) if parsed.is_integer() else parsed
    except (TypeError, ValueError):
        return None


def _rate(value: Any) -> float | None:
    parsed = _number(value)
    if parsed is None:
        return None
    # Some imported datasets store rates as percentages rather than decimals.
    if 1 < parsed <= 100:
        parsed = parsed / 100
    return round(float(parsed), 4) if 0 <= parsed <= 1 else None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            decoded = json.loads(stripped)
            if decoded != value:
                return _string_list(decoded)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        return [part.strip() for part in re.split(r"[,;|]", stripped) if part.strip()]
    if isinstance(value, dict):
        return [str(key) for key, present in value.items() if present]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return None


def _stable_college_id(row: dict) -> str:
    explicit = _first(row, "college_id", "school_id", "unit_id", "unitid", "id")
    if explicit is not None:
        return str(explicit)
    identity = "|".join(
        str(_first(row, key) or "").lower()
        for key in ("name", "city", "state")
    )
    return f"halda-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def _requested_program(filters: dict, profile: dict) -> str | None:
    programs = filters.get("programs") or []
    if programs:
        return str(programs[0])
    intended = profile.get("academic", {}).get("intended_major")
    return str(intended) if intended else None


def _program_status(row: dict, requested: str | None) -> tuple[str, str | None]:
    cip_code = _first(row, "cip_code", "program_cip_code", "cip")
    if not requested:
        return "unknown", str(cip_code) if cip_code else None

    requested_lower = requested.lower()
    programs = _string_list(_first(row, "programs", "program_names", "majors"))
    if programs is not None:
        available = any(
            requested_lower in program.lower() or program.lower() in requested_lower
            for program in programs
        )
        return ("available" if available else "unavailable"), str(cip_code) if cip_code else None

    flag_aliases = []
    if "nurs" in requested_lower:
        flag_aliases = ["has_nursing", "offers_nursing", "nursing"]
    elif "computer science" in requested_lower or requested_lower == "cs":
        flag_aliases = ["has_cs", "offers_cs", "computer_science"]
    elif "engineer" in requested_lower:
        flag_aliases = ["has_engineering", "offers_engineering", "engineering"]

    for alias in flag_aliases:
        if alias in row:
            available = _boolean(row.get(alias))
            if available is not None:
                return ("available" if available else "unavailable"), str(cip_code) if cip_code else None

    return "unknown", str(cip_code) if cip_code else None


def _classification(row: dict, profile: dict, admission_rate: float | None) -> dict:
    student_gpa = _number(profile.get("academic", {}).get("gpa"))
    gpa_low = _number(_first(row, "gpa_25th", "gpa_25", "admitted_gpa_25th"))
    gpa_high = _number(_first(row, "gpa_75th", "gpa_75", "admitted_gpa_75th"))
    typical_gpa = _number(_first(row, "average_gpa", "avg_gpa", "admitted_gpa"))

    academic_signal = None
    academic_evidence = None
    if student_gpa is not None and gpa_low is not None and gpa_high is not None:
        if student_gpa < gpa_low:
            academic_signal = "below"
        elif student_gpa > gpa_high:
            academic_signal = "above"
        else:
            academic_signal = "within"
        academic_evidence = (
            f"Your {student_gpa:g} GPA is {academic_signal} the institution's "
            f"reported {gpa_low:g}-{gpa_high:g} GPA range."
        )
    elif student_gpa is not None and typical_gpa is not None:
        difference = float(student_gpa) - float(typical_gpa)
        if difference < -GPA_MARGIN:
            academic_signal = "below"
        elif difference >= GPA_MARGIN:
            academic_signal = "above"
        else:
            academic_signal = "within"
        academic_evidence = (
            f"Your {student_gpa:g} GPA is {academic_signal} the institution's "
            f"reported {typical_gpa:g} typical GPA."
        )

    rate_evidence = (
        f"The institution's overall admission rate is {admission_rate:.0%}."
        if admission_rate is not None
        else None
    )

    # Extreme selectivity dominates a simple GPA comparison. Strong academics
    # may improve fit, but they do not turn a <=20% admit-rate school into a
    # deterministic target or likely classification.
    if admission_rate is not None and admission_rate <= HIGHLY_SELECTIVE_RATE:
        return {
            "label": "reach",
            "reason": " ".join(part for part in (academic_evidence, rate_evidence) if part),
            "basis": (
                "student_academic_profile"
                if academic_evidence
                else "admission_rate_only"
            ),
        }

    if academic_signal is not None:
        if academic_signal == "below":
            label = "reach"
        elif academic_signal == "above" and (
            admission_rate is None or admission_rate >= 0.50
        ):
            label = "likely"
        else:
            label = "target"
        return {
            "label": label,
            "reason": " ".join(part for part in (academic_evidence, rate_evidence) if part),
            "basis": "student_academic_profile",
        }

    if admission_rate is not None:
        if admission_rate <= REACH_RATE:
            label = "reach"
        elif admission_rate <= LIKELY_RATE:
            label = "target"
        else:
            label = "likely"
        return {
            "label": label,
            "reason": (
                f"{rate_evidence} This estimate uses admission rate only because "
                "comparable student GPA data is unavailable."
            ),
            "basis": "admission_rate_only",
        }

    return {
        "label": "unknown",
        "reason": "There is not enough admissions data to estimate fit.",
        "basis": "insufficient_data",
    }


def _match_score(row: dict) -> float | None:
    raw = _number(_first(row, "match_score", "similarity", "score"))
    if raw is None:
        return None
    if raw <= 1:
        raw *= 100
    return round(min(float(raw), 100), 1)


def _source(row: dict, college_id: str, fields: list[str], retrieved_at: str) -> dict:
    name = _first(row, "source_name", "data_source") or DEFAULT_SOURCE_NAME
    url = _first(row, "source_url", "scorecard_url")
    if not url:
        url = (
            f"https://collegescorecard.ed.gov/school/?{college_id}"
            if college_id.isdigit()
            else "https://collegescorecard.ed.gov/"
        )
    source_time = _first(row, "source_retrieved_at", "retrieved_at", "updated_at") or retrieved_at
    return {
        "name": str(name),
        "url": str(url),
        "retrieved_at": str(source_time),
        "fields": fields or ["name", "location"],
    }


def _match_reasons(
    *,
    net_price: float | int | None,
    budget: float | int | None,
    requested_program: str | None,
    program_status: str,
    classification: dict,
    graduation_rate: float | None,
    median_earnings: float | int | None,
    match_score: float | None,
    state: str | None,
    filters: dict,
    query: str,
) -> list[dict]:
    reasons = []
    if requested_program and program_status != "unknown":
        reasons.append({
            "category": "program",
            "text": (
                f"The institution reports offering {requested_program}."
                if program_status == "available"
                else f"The available source does not list {requested_program}."
            ),
            "evidence": f"Program status: {program_status}",
        })
    if net_price is not None and budget is not None:
        difference = budget - net_price
        reasons.append({
            "category": "financial",
            "text": (
                "The reported net price is within your annual budget."
                if difference >= 0
                else "The reported net price is above your annual budget."
            ),
            "evidence": (
                f"${net_price:,.0f} net price versus a ${budget:,.0f} budget"
            ),
        })
    if classification.get("label") != "unknown":
        reasons.append({
            "category": "academic",
            "text": (
                f"This school is classified as {classification['label']} based on "
                "the available admissions evidence."
            ),
            "evidence": classification["reason"],
        })
    requested_states = filters.get("location_state") or []
    if state and state in requested_states:
        reasons.append({
            "category": "location",
            "text": "The institution is in one of your requested states.",
            "evidence": state,
        })
    if graduation_rate is not None or median_earnings is not None:
        evidence = []
        if graduation_rate is not None:
            evidence.append(f"{graduation_rate:.0%} graduation rate")
        if median_earnings is not None:
            evidence.append(f"${median_earnings:,.0f} median earnings 10 years after entry")
        reasons.append({
            "category": "outcomes",
            "text": "Reported completion and earnings outcomes help measure long-term value.",
            "evidence": "; ".join(evidence),
        })
    if not reasons:
        reasons.append({
            "category": "culture",
            "text": "The institution matched the interests expressed in your search.",
            "evidence": (
                f"Semantic match {match_score:.0f}/100 for: {query}"
                if match_score is not None and query
                else query or None
            ),
        })
    return reasons[:5]


def normalize_college_row(
    row: dict,
    *,
    profile: dict,
    filters: dict,
    query: str,
    retrieved_at: str,
) -> dict:
    college_id = _stable_college_id(row)
    name = _first(row, "name", "school_name", "institution_name") or "Unknown institution"
    city = _first(row, "city", "school_city")
    state = _first(row, "state", "state_code", "school_state")
    net_price = _number(_first(row, "net_price", "avg_net_price", "average_net_price"))
    budget = _number(profile.get("hard_constraints", {}).get("max_cost"))
    if budget is None:
        budget = _number(filters.get("max_net_price"))
    admission_rate = _rate(_first(row, "admission_rate", "acceptance_rate", "admissions_rate"))
    graduation_rate = _rate(_first(row, "graduation_rate", "completion_rate", "completion_rate_4yr"))
    earnings = _number(_first(
        row,
        "median_earnings_10yr",
        "median_earnings",
        "earnings_10yr",
        "median_earnings_10_years",
    ))
    program = _requested_program(filters, profile)
    program_status, cip_code = _program_status(row, program)
    classification = _classification(row, profile, admission_rate)
    match_score = _match_score(row)

    source_fields = []
    for value, field in (
        (net_price, "financials.net_price"),
        (admission_rate, "admissions.admission_rate"),
        (graduation_rate, "outcomes.graduation_rate"),
        (earnings, "outcomes.median_earnings_10yr"),
    ):
        if value is not None:
            source_fields.append(field)
    if program_status != "unknown":
        source_fields.append("program")
    if _first(
        row,
        "gpa_25th",
        "gpa_25",
        "admitted_gpa_25th",
        "gpa_75th",
        "gpa_75",
        "admitted_gpa_75th",
        "average_gpa",
        "avg_gpa",
        "admitted_gpa",
    ) is not None:
        source_fields.append("classification.gpa_comparison")

    difference = budget - net_price if budget is not None and net_price is not None else None
    return {
        "college_id": college_id,
        "name": str(name),
        "location": {
            "city": str(city) if city is not None else None,
            "state": str(state) if state is not None else None,
        },
        "classification": classification,
        "match_score": match_score,
        "match_reasons": _match_reasons(
            net_price=net_price,
            budget=budget,
            requested_program=program,
            program_status=program_status,
            classification=classification,
            graduation_rate=graduation_rate,
            median_earnings=earnings,
            match_score=match_score,
            state=str(state) if state is not None else None,
            filters=filters,
            query=query,
        ),
        "financials": {
            "currency": "USD",
            "net_price": net_price,
            "student_budget": budget,
            "budget_difference": difference,
            "within_budget": difference >= 0 if difference is not None else None,
        },
        "admissions": {"admission_rate": admission_rate},
        "outcomes": {
            "graduation_rate": graduation_rate,
            "median_earnings_10yr": earnings,
        },
        "program": {
            "requested": program,
            "status": program_status,
            "cip_code": cip_code,
        },
        "sources": [_source(row, college_id, source_fields, retrieved_at)],
    }


def normalize_college_results(
    rows: list[dict] | None,
    *,
    profile: dict,
    filters: dict,
    query: str,
    now: datetime | None = None,
) -> dict:
    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated_at_text = generated_at.isoformat().replace("+00:00", "Z")
    program = _requested_program(filters, profile)
    budget = _number(profile.get("hard_constraints", {}).get("max_cost"))
    if budget is None:
        budget = _number(filters.get("max_net_price"))

    return {
        "schema_version": SCHEMA_VERSION,
        "event": EVENT_NAME,
        "recommendation_set_id": f"rec_{uuid.uuid4().hex}",
        "generated_at": generated_at_text,
        "query": {
            "text": query,
            "requested_program": program,
            "student_budget_usd": budget,
        },
        "colleges": [
            normalize_college_row(
                row,
                profile=profile,
                filters=filters,
                query=query,
                retrieved_at=generated_at_text,
            )
            for row in (rows or [])[:10]
        ],
    }
