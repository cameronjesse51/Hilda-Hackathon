import json
import logging

try:
    from backend.agent.profile import merge_profile_update
    from backend.agent.internship import (
        start_internship,
        get_active_internship,
        get_next_probe,
        record_probe_score,
    )
except ModuleNotFoundError:
    from agent.profile import merge_profile_update
    from agent.internship import (
        start_internship,
        get_active_internship,
        get_next_probe,
        record_probe_score,
    )

log = logging.getLogger(__name__)


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

def _handle_search_colleges(tool_input: dict, profile: dict) -> tuple[str, dict]:
    query = tool_input.get("query", "")
    filters = tool_input.get("filters", {})
    limit = tool_input.get("limit", 5)
    log.info("search_colleges called: query=%s filters=%s", query, json.dumps(filters))

    db, oai = _get_clients()

    try:
        res = oai.embeddings.create(
            input=query if query else "good college",
            model="text-embedding-3-small",
            dimensions=1024
        )
        query_embedding = res.data[0].embedding
    except Exception as e:
        log.error("Embedding failed: %s", e)
        return json.dumps({"error": "Failed to generate semantic embedding"}), profile

    programs = filters.get("programs", [])
    programs_lower = [p.lower() for p in programs]

    rpc_params = {
        "query_embedding": query_embedding,
        "max_net_price": filters.get("max_net_price"),
        "filter_visa": filters.get("visa_friendly"),
        "filter_state": filters.get("location_state"),
        "min_admission_rate": filters.get("min_acceptance_rate"),
        "max_admission_rate": filters.get("max_acceptance_rate"),
        "requires_nursing": any("nursing" in p for p in programs_lower),
        "requires_cs": any("computer science" in p or "cs" in p for p in programs_lower),
        "requires_engineering": any("engineering" in p for p in programs_lower),
        "match_count": limit
    }

    try:
        response = db.rpc('search_colleges', rpc_params).execute()
        results = response.data
    except Exception as e:
        log.error("Supabase RPC failed: %s", e)
        return json.dumps({"error": "Database query failed"}), profile

    return json.dumps({
        "results": results,
        "note": "Real results from Supabase hybrid search."
    }), profile


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
