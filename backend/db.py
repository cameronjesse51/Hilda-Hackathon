import asyncio
import json
import os
import uuid

from supabase import create_client

try:
    from backend.phone import normalize_phone_e164
except ModuleNotFoundError:
    from phone import normalize_phone_e164


def _client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _parse_list(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        return json.loads(val)
    except Exception:
        return []


def _parse_dict(val):
    if not val:
        return {}
    if isinstance(val, dict):
        return val
    try:
        return json.loads(val)
    except Exception:
        return {}


def _normalize_student_id(student_id: str) -> str:
    return str(uuid.UUID(str(student_id)))


def _row_to_profile(row: dict) -> dict:
    student_id = _normalize_student_id(row["student_id"])
    return {
        "student_id": student_id,
        "contact": {
            "first_name": row.get("first_name", ""),
            "last_name": row.get("last_name", ""),
            "email": row.get("email", ""),
            "phone": row.get("phone", ""),
            "zip": row.get("zip", ""),
            "high_school": row.get("high_school", ""),
        },
        "academic": {
            "grade": row.get("grade", ""),
            "gpa": row.get("gpa"),
            "test_scores": _parse_dict(row.get("test_scores")),
            "intended_major": row.get("intended_major", ""),
            "transfer_credits": row.get("transfer_credits"),
        },
        "stated": {
            "interests": _parse_list(row.get("interests")),
            "career_goals": _parse_list(row.get("career_goals")),
            "location_pref": _parse_list(row.get("location_pref")),
            "school_size_pref": row.get("school_size_pref", ""),
        },
        "inferred": {
            "learning_style": row.get("learning_style", ""),
            "risk_tolerance": row.get("risk_tolerance", ""),
            "collaboration_pref": row.get("collaboration_pref", ""),
            "ambiguity_tolerance": row.get("ambiguity_tolerance", ""),
        },
        "behavioral": {
            "probe_responses": row.get("probe_responses") or [],
            "micro_internship_results": row.get("micro_internship_results") or [],
            "velocity_signals": {
                "causal_reasoning": row.get("velocity_causal_reasoning"),
                "quantitative": row.get("velocity_quantitative"),
                "ambiguity_tolerance": row.get("velocity_ambiguity_tolerance"),
            },
            "domain_affinities": _parse_dict(row.get("domain_affinities")),
        },
        "hard_constraints": {
            "max_cost": row.get("max_cost"),
            "visa_required": row.get("visa_required", False),
            "transfer_student": row.get("transfer_student", False),
            "commuter": row.get("commuter", False),
        },
        "confidence_scores": {
            "career_clarity": row.get("career_clarity", 0.0),
            "major_fit": row.get("major_fit", 0.0),
            "culture_fit": row.get("culture_fit", 0.0),
            "financial_fit": row.get("financial_fit", 0.0),
        },
        "stage": row.get("stage", "sophomore"),
        "session_history": row.get("session_history") or [],
    }


def _profile_to_row(profile: dict) -> dict:
    student_id = _normalize_student_id(profile["student_id"])
    phone = normalize_phone_e164(profile["contact"]["phone"])
    profile["student_id"] = student_id
    profile["contact"]["phone"] = phone
    return {
        "student_id": student_id,
        "phone": phone,
        "first_name": profile["contact"]["first_name"],
        "last_name": profile["contact"]["last_name"],
        "email": profile["contact"]["email"],
        "zip": profile["contact"]["zip"],
        "high_school": profile["contact"]["high_school"],
        "grade": profile["academic"]["grade"],
        "gpa": profile["academic"]["gpa"],
        "test_scores": json.dumps(profile["academic"]["test_scores"]) if profile["academic"]["test_scores"] else None,
        "intended_major": profile["academic"]["intended_major"],
        "transfer_credits": profile["academic"]["transfer_credits"],
        "interests": json.dumps(profile["stated"]["interests"]),
        "career_goals": json.dumps(profile["stated"]["career_goals"]),
        "location_pref": json.dumps(profile["stated"]["location_pref"]),
        "school_size_pref": profile["stated"]["school_size_pref"],
        "learning_style": profile["inferred"]["learning_style"],
        "risk_tolerance": profile["inferred"]["risk_tolerance"],
        "collaboration_pref": profile["inferred"]["collaboration_pref"],
        "ambiguity_tolerance": profile["inferred"]["ambiguity_tolerance"],
        "probe_responses": profile["behavioral"]["probe_responses"],
        "micro_internship_results": profile["behavioral"]["micro_internship_results"],
        "velocity_causal_reasoning": profile["behavioral"]["velocity_signals"]["causal_reasoning"],
        "velocity_quantitative": profile["behavioral"]["velocity_signals"]["quantitative"],
        "velocity_ambiguity_tolerance": profile["behavioral"]["velocity_signals"]["ambiguity_tolerance"],
        "domain_affinities": profile["behavioral"]["domain_affinities"],
        "max_cost": profile["hard_constraints"]["max_cost"],
        "visa_required": profile["hard_constraints"]["visa_required"],
        "transfer_student": profile["hard_constraints"]["transfer_student"],
        "commuter": profile["hard_constraints"]["commuter"],
        "career_clarity": profile["confidence_scores"]["career_clarity"],
        "major_fit": profile["confidence_scores"]["major_fit"],
        "culture_fit": profile["confidence_scores"]["culture_fit"],
        "financial_fit": profile["confidence_scores"]["financial_fit"],
        "stage": profile["stage"],
        "session_history": profile["session_history"],
    }


def _sync_get_profile(student_id: str):
    student_id = _normalize_student_id(student_id)
    result = _client().table("student_profiles").select("*").eq("student_id", student_id).execute()
    if result.data:
        return _row_to_profile(result.data[0])
    return None


def _sync_get_profile_by_phone(phone: str):
    phone = normalize_phone_e164(phone)
    result = _client().table("student_profiles").select("*").eq("phone", phone).execute()
    if result.data:
        return _row_to_profile(result.data[0])
    return None


def _sync_save_profile(profile: dict):
    student_id = _normalize_student_id(profile["student_id"])
    existing = (
        _client()
        .table("student_profiles")
        .select("student_id,phone")
        .eq("student_id", student_id)
        .execute()
    )
    if existing.data:
        # The verified login phone is an identity attribute, not agent-editable profile data.
        profile["contact"]["phone"] = existing.data[0]["phone"]
    row = _profile_to_row(profile)
    if existing.data:
        _client().table("student_profiles").update(row).eq("student_id", student_id).execute()
    else:
        _client().table("student_profiles").insert(row).execute()


def _sync_save_messages(student_id: str, messages: list):
    student_id = _normalize_student_id(student_id)
    _client().table("student_profiles").update({"session_history": messages}).eq("student_id", student_id).execute()


def _sync_list_recommendation_sets(student_id: str, limit: int):
    student_id = _normalize_student_id(student_id)
    result = (
        _client()
        .table("college_recommendation_sets")
        .select("id,schema_version,query,recommendations,created_at")
        .eq("student_id", student_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 50)))
        .execute()
    )
    return result.data or []


def _sync_get_recommendation_set(student_id: str, recommendation_set_id: str):
    student_id = _normalize_student_id(student_id)
    result = (
        _client()
        .table("college_recommendation_sets")
        .select("id,schema_version,query,recommendations,profile_snapshot,created_at")
        .eq("student_id", student_id)
        .eq("id", recommendation_set_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def _sync_get_or_create_profile(phone: str):
    phone = normalize_phone_e164(phone)
    existing = _sync_get_profile_by_phone(phone)
    if existing:
        return existing

    try:
        from backend.agent.profile import empty_profile
    except ModuleNotFoundError:
        from agent.profile import empty_profile

    profile = empty_profile(str(uuid.uuid4()))
    profile["contact"]["phone"] = phone
    try:
        _sync_save_profile(profile)
        return profile
    except Exception:
        # A concurrent verification may have inserted the unique phone first.
        existing = _sync_get_profile_by_phone(phone)
        if existing:
            return existing
        raise


async def get_profile(student_id: str):
    return await asyncio.to_thread(_sync_get_profile, student_id)


async def get_profile_by_phone(phone: str):
    return await asyncio.to_thread(_sync_get_profile_by_phone, phone)


async def get_or_create_profile(phone: str):
    return await asyncio.to_thread(_sync_get_or_create_profile, phone)


async def save_profile(profile: dict):
    await asyncio.to_thread(_sync_save_profile, profile)


async def save_messages(student_id: str, messages: list):
    await asyncio.to_thread(_sync_save_messages, student_id, messages)


async def list_recommendation_sets(student_id: str, limit: int = 10):
    return await asyncio.to_thread(_sync_list_recommendation_sets, student_id, limit)


async def get_recommendation_set(student_id: str, recommendation_set_id: str):
    return await asyncio.to_thread(
        _sync_get_recommendation_set,
        student_id,
        recommendation_set_id,
    )
