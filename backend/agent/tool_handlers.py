from __future__ import annotations

import json
import logging
import re

try:
    from backend.agent.profile import merge_profile_update
    from backend.agent.college_recommendations import normalize_college_results
    from backend.agent.internship import (
        start_internship,
        get_active_internship,
        get_next_probe,
        record_probe_score,
    )
except ModuleNotFoundError:
    from agent.profile import merge_profile_update
    from agent.college_recommendations import normalize_college_results
    from agent.internship import (
        start_internship,
        get_active_internship,
        get_next_probe,
        record_probe_score,
    )

log = logging.getLogger(__name__)


STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}
STATE_CODES = frozenset(STATE_NAMES.values())
VOCATIONAL_TERMS = (
    "trade school", "vocational", "certificate", "cosmetology", "barber",
    "beauty school", "esthetic", "welding", "automotive", "career school",
)
COLLEGE_SELECT_FIELDS = ",".join((
    "unitid", "name", "city", "state", "admission_rate", "sat_avg", "enrollment",
    "control", "size_category", "highest_degree", "pred_degree", "net_price_pub",
    "net_price_priv", "net_price_income1", "graduation_rate", "transfer_rate",
    "pct_international", "visa_friendly", "pct_pell", "pct_cs", "pct_engineering",
    "pct_biology", "pct_nursing", "median_earnings_10y", "median_grad_debt",
    "prestige_tier", "vibe_description", "ranking",
))


def _location_states(query: str, filters: dict) -> list[str]:
    """Return explicit state filters, or deterministically recover them from the query."""
    explicit = filters.get("location_state") or []
    if isinstance(explicit, str):
        explicit = [explicit]
    normalized = []
    for value in explicit:
        state = str(value).strip()
        code = STATE_NAMES.get(state.lower(), state.upper())
        if code in STATE_CODES and code not in normalized:
            normalized.append(code)
    if normalized:
        return normalized

    query_lower = query.lower()
    for name, code in STATE_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", query_lower) and code not in normalized:
            normalized.append(code)
    # Only recognize abbreviations when the user/model preserved uppercase. This avoids
    # interpreting ordinary words such as "in" and "or" as state codes.
    for code in re.findall(r"(?<![A-Za-z])([A-Z]{2})(?![A-Za-z])", query):
        if code in STATE_CODES and code not in normalized:
            normalized.append(code)
    return normalized


def _is_vocational_query(query: str, programs: list[str]) -> bool:
    text = " ".join([query, *[str(program) for program in programs]]).lower()
    return any(term in text for term in VOCATIONAL_TERMS)


def _number_or_none(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _canonicalize_college_row(row: dict) -> dict:
    """Adapt Supabase's structured columns to the existing recommendation normalizer."""
    result = dict(row)
    if result.get("net_price") is None:
        control = result.get("control")
        result["net_price"] = (
            result.get("net_price_pub") if control == 1 else result.get("net_price_priv")
        )
        if result["net_price"] is None:
            result["net_price"] = result.get("net_price_pub") or result.get("net_price_priv")
    if result.get("median_earnings_10yr") is None:
        result["median_earnings_10yr"] = result.get("median_earnings_10y")
    for program, field in (
        ("nursing", "pct_nursing"),
        ("cs", "pct_cs"),
        ("engineering", "pct_engineering"),
    ):
        percentage = _number_or_none(result.get(field))
        if percentage is not None:
            result[f"has_{program}"] = percentage > 0
    return result


def _requested_program_field(programs: list[str]) -> str | None:
    text = " ".join(str(program).lower() for program in programs)
    if "nurs" in text:
        return "pct_nursing"
    if "computer science" in text or re.search(r"\bcs\b", text):
        return "pct_cs"
    if "engineer" in text:
        return "pct_engineering"
    if "biology" in text or "biological" in text:
        return "pct_biology"
    return None


def _requested_program_name(filters: dict, profile: dict) -> str | None:
    programs = filters.get("programs") or []
    if programs:
        return str(programs[0])
    intended_major = profile.get("academic", {}).get("intended_major")
    return str(intended_major) if intended_major else None


def _college_rpc_params(
    query_embedding: list[float], filters: dict, profile: dict, limit: int
) -> dict:
    programs = filters.get("programs") or []
    programs_lower = [str(program).lower() for program in programs]
    return {
        "query_embedding": query_embedding,
        "max_net_price": filters.get("max_net_price"),
        "filter_visa": filters.get("visa_friendly"),
        "filter_state": filters.get("location_state"),
        "min_admission_rate": filters.get("min_acceptance_rate"),
        "max_admission_rate": filters.get("max_acceptance_rate"),
        "requires_nursing": any("nursing" in program for program in programs_lower),
        "requires_cs": any(
            "computer science" in program or program == "cs"
            for program in programs_lower
        ),
        "requires_engineering": any(
            "engineering" in program for program in programs_lower
        ),
        "filter_school_size": filters.get("school_size"),
        "requested_program": _requested_program_name(filters, profile),
        "match_count": limit,
    }


def _matches_college_constraints(row: dict, filters: dict, *, vocational: bool) -> bool:
    states = filters.get("location_state") or []
    if states and row.get("state") not in states:
        return False

    predominant_degree = _number_or_none(row.get("pred_degree"))
    if not vocational and predominant_degree is not None and predominant_degree < 2:
        return False

    size = filters.get("school_size")
    if size and row.get("size_category") != size:
        return False
    if filters.get("visa_friendly") is True and row.get("visa_friendly") is not True:
        return False

    admission_rate = _number_or_none(row.get("admission_rate"))
    minimum = _number_or_none(filters.get("min_acceptance_rate"))
    maximum = _number_or_none(filters.get("max_acceptance_rate"))
    if minimum is not None and (admission_rate is None or admission_rate < minimum):
        return False
    if maximum is not None and (admission_rate is None or admission_rate > maximum):
        return False

    max_price = _number_or_none(filters.get("max_net_price"))
    net_price = _number_or_none(row.get("net_price"))
    if max_price is not None and (net_price is None or net_price > max_price):
        return False

    program_field = _requested_program_field(filters.get("programs") or [])
    if program_field:
        share = _number_or_none(row.get(program_field))
        if share is None or share <= 0:
            return False
    return True


def _structured_rank(row: dict, filters: dict) -> tuple:
    program_field = _requested_program_field(filters.get("programs") or [])
    program_share = _number_or_none(row.get(program_field)) if program_field else None
    ranking = _number_or_none(row.get("ranking"))
    graduation = _number_or_none(row.get("graduation_rate"))
    earnings = _number_or_none(row.get("median_earnings_10y"))
    return (
        0 if program_share is not None else 1,
        -(program_share or 0),
        0 if ranking is not None else 1,
        ranking or 999999,
        -(graduation or 0),
        -(earnings or 0),
        str(row.get("name") or ""),
    )


def _enrich_semantic_rows(db, rows: list[dict]) -> list[dict]:
    ids = [str(row.get("unitid")) for row in rows if row.get("unitid") is not None]
    if not ids:
        return [_canonicalize_college_row(row) for row in rows]
    try:
        details = (
            db.table("college_embeddings")
            .select(COLLEGE_SELECT_FIELDS)
            .in_("unitid", ids)
            .execute()
            .data or []
        )
        by_id = {str(row.get("unitid")): row for row in details}
        return [
            _canonicalize_college_row({**by_id.get(str(row.get("unitid")), {}), **row})
            for row in rows
        ]
    except Exception as exc:
        log.warning("Could not enrich semantic college rows: %s", exc)
        return [_canonicalize_college_row(row) for row in rows]


def _structured_fallback_rows(db, filters: dict, query: str, limit: int) -> list[dict]:
    programs = filters.get("programs") or []
    vocational = _is_vocational_query(query, programs)
    try:
        request = (
            db.table("college_embeddings")
            .select(COLLEGE_SELECT_FIELDS)
            .is_("embedding", "null")
            .gte("pred_degree", 1 if vocational else 2)
        )
        states = filters.get("location_state") or []
        if states:
            request = request.in_("state", states)
        response = (
            request
            .order("ranking", desc=False, nullsfirst=False)
            .order("graduation_rate", desc=True, nullsfirst=False)
            .limit(max(100, min(limit * 40, 500)))
            .execute()
        )
        rows = [_canonicalize_college_row(row) for row in (response.data or [])]
        eligible = [
            row for row in rows
            if _matches_college_constraints(row, filters, vocational=vocational)
        ]
        return sorted(eligible, key=lambda row: _structured_rank(row, filters))[:limit]
    except Exception as exc:
        log.error("Structured college fallback failed: %s", exc)
        return []


def _combine_college_results(
    semantic_rows: list[dict], fallback_rows: list[dict], filters: dict, query: str, limit: int
) -> list[dict]:
    vocational = _is_vocational_query(query, filters.get("programs") or [])
    combined = []
    seen = set()
    for row in [*semantic_rows, *fallback_rows]:
        row = _canonicalize_college_row(row)
        if not _matches_college_constraints(row, filters, vocational=vocational):
            continue
        college_id = str(row.get("unitid") or row.get("id") or "")
        if not college_id or college_id in seen:
            continue
        seen.add(college_id)
        combined.append(row)
        if len(combined) >= limit:
            break
    return combined


def handle_tool_call(name: str, tool_input: dict, profile: dict) -> tuple[str, dict]:
    handler = HANDLERS.get(name)
    if not handler:
        return f"Unknown tool: {name}", profile
    return handler(tool_input, profile)


def _handle_update_profile(tool_input: dict, profile: dict) -> tuple[str, dict]:
    profile = merge_profile_update(profile, tool_input)
    updated_fields = [k for k, v in tool_input.items() if v]
    return f"Profile updated: {', '.join(updated_fields)}", profile


def _handle_probe_concept(tool_input: dict, profile: dict) -> tuple[str, dict]:
    domain = tool_input.get("domain", "")
    concept = tool_input.get("concept", "")
    probe_type = tool_input.get("probe_type", "")
    difficulty = tool_input.get("difficulty", 0.3)

    internship = get_active_internship(profile)
    if not internship or internship["domain"] != domain:
        internship = start_internship(profile, domain)
        if not internship:
            return f"Unknown domain: {domain}. Cannot start micro-internship.", profile
        log.info("Started micro-internship: %s for domain %s", internship["internship_id"], domain)

    next_probe = get_next_probe(internship)

    profile.setdefault("behavioral", {}).setdefault("probe_responses", []).append({
        "domain": domain,
        "concept": concept,
        "probe_type": probe_type,
        "difficulty": difficulty,
        "response": None,
    })

    instructions = (
        f"Micro-internship active: {domain}, module {internship['current_module']}. "
        f"Deliver a {probe_type} on '{concept}' at difficulty {difficulty}. "
    )
    if probe_type == "intuition_probe":
        instructions += "Ask BEFORE teaching — get their gut feeling first."
    elif probe_type == "comprehension_check":
        instructions += "Teach the concept first, then check understanding."
    elif probe_type == "retention_check":
        instructions += "Revisit the concept with different framing."
    elif probe_type == "transfer_probe":
        instructions += "Ask them to apply the concept to a completely new context."

    return instructions, profile


def _handle_score_probe_response(tool_input: dict, profile: dict) -> tuple[str, dict]:
    domain = tool_input.get("domain", "")
    concept = tool_input.get("concept", "")
    probe_type = tool_input.get("probe_type", "")
    score = tool_input.get("score", 0.0)
    reasoning = tool_input.get("reasoning", "")

    internship = get_active_internship(profile)
    if not internship:
        return "No active micro-internship to score.", profile

    record_probe_score(internship, probe_type, concept, score)
    log.info(
        "Probe scored: %s/%s %s = %.2f (%s)",
        domain, concept, probe_type, score, reasoning,
    )

    next_probe = get_next_probe(internship)
    if not next_probe:
        velocity = internship.get("overall_domain_velocity")
        traits = internship.get("inferred_traits", [])
        return (
            f"Micro-internship complete for {domain}! "
            f"Overall velocity: {velocity}. Traits: {', '.join(traits) if traits else 'computing...'}. "
            "Share insights about what you learned about this student's learning style."
        ), profile

    return (
        f"Score recorded: {probe_type}={score}. "
        f"Next: {next_probe['probe_type']} on '{next_probe['concept']}' "
        f"(module {next_probe['module']}, difficulty {next_probe['difficulty']}). "
        "Continue the conversation naturally and deliver the next probe."
    ), profile


supabase_client = None
openai_client = None

def _get_clients():
    global supabase_client, openai_client
    import os
    if not supabase_client:
        from supabase import create_client
        supabase_client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    if not openai_client:
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
    return supabase_client, openai_client


def _recommendation_record(payload: dict, profile: dict) -> dict:
    """Build a persistence row without copying contact details or chat history."""
    return {
        "id": payload["recommendation_set_id"],
        "student_id": profile["student_id"],
        "schema_version": payload["schema_version"],
        "query": payload["query"],
        "recommendations": payload["colleges"],
        "profile_snapshot": {
            "academic": profile.get("academic", {}),
            "stated": profile.get("stated", {}),
            "hard_constraints": profile.get("hard_constraints", {}),
            "confidence_scores": profile.get("confidence_scores", {}),
            "stage": profile.get("stage"),
        },
        "created_at": payload["generated_at"],
    }

def _handle_search_colleges(tool_input: dict, profile: dict) -> tuple[str, dict]:
    query = tool_input.get("query", "")
    filters = dict(tool_input.get("filters", {}))
    recovered_states = _location_states(query, filters)
    if not recovered_states:
        profile_locations = profile.get("stated", {}).get("location_pref") or []
        if isinstance(profile_locations, str):
            profile_locations = [profile_locations]
        recovered_states = _location_states(" ".join(profile_locations), {})
    if recovered_states:
        filters["location_state"] = recovered_states
    limit = max(1, min(int(tool_input.get("limit", 5)), 10))
    log.info("search_colleges called: query=%s filters=%s", query, json.dumps(filters))

    db, oai = _get_clients()

    query_embedding = None
    try:
        res = oai.embeddings.create(
            input=query if query else "good college",
            model="text-embedding-3-small",
            dimensions=1024
        )
        query_embedding = res.data[0].embedding
    except Exception as e:
        log.error("Embedding failed: %s", e)

    rpc_params = _college_rpc_params(query_embedding, filters, profile, limit)

    semantic_results = []
    if query_embedding is not None:
        try:
            response = db.rpc('search_colleges', rpc_params).execute()
            semantic_results = _enrich_semantic_rows(db, response.data or [])
        except Exception as e:
            log.error("Supabase semantic RPC failed; using structured fallback: %s", e)

    # Fetch enough structured rows to replace semantic results that violate hard
    # constraints and fill slots when the matching schools have no embedding.
    fallback_results = _structured_fallback_rows(db, filters, query, limit)
    results = _combine_college_results(
        semantic_results,
        fallback_results,
        filters,
        query,
        limit,
    )

    normalized = normalize_college_results(
        results,
        profile=profile,
        filters=filters,
        query=query,
        comparison_requested=tool_input.get("comparison_requested", False),
    )
    try:
        db.table("college_recommendation_sets").insert(
            _recommendation_record(normalized, profile)
        ).execute()
    except Exception as e:
        # Search results remain useful if persistence is temporarily degraded.
        log.error("Failed to persist recommendation set: %s", e)
    return json.dumps(normalized), profile


def _handle_schedule_checkin(tool_input: dict, profile: dict) -> tuple[str, dict]:
    channel = tool_input.get("channel", "sms")
    send_at = tool_input.get("send_at", "")
    topic = tool_input.get("topic", "")
    message_body = tool_input.get("message_body", "")
    student_id = profile.get("student_id")
    
    log.info(
        "schedule_checkin: channel=%s send_at=%s topic=%s body=%s",
        channel, send_at, topic, message_body,
    )

    db, _ = _get_clients()

    if not student_id:
        log.warning("schedule_checkin failed: no student_id in profile")
        return "Failed to schedule check-in: No student_id found in profile.", profile

    try:
        db.table("scheduled_checkins").insert({
            "student_id": student_id,
            "send_at": send_at,
            "channel": channel,
            "topic": topic,
            "message_body": message_body
        }).execute()
    except Exception as e:
        log.error("Failed to insert scheduled check-in: %s", e)
        return f"Database error scheduling check-in: {str(e)}", profile

    return (
        f"Check-in scheduled: {topic} via {channel} at {send_at}. "
        "Message will be delivered by the backend job runner."
    ), profile


HANDLERS = {
    "update_profile": _handle_update_profile,
    "probe_concept": _handle_probe_concept,
    "search_colleges": _handle_search_colleges,
    "schedule_checkin": _handle_schedule_checkin,
    "score_probe_response": _handle_score_probe_response,
}
