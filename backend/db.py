import asyncio
import json
import os

from supabase import create_client


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


def _row_to_profile(row: dict, student_id: str) -> dict:
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
    return {
        "phone": profile["student_id"],
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
    result = _client().table("student_profiles").select("*").eq("phone", student_id).execute()
    if result.data:
        return _row_to_profile(result.data[0], student_id)
    return None


def _sync_save_profile(profile: dict):
    row = _profile_to_row(profile)
    existing = _client().table("student_profiles").select("phone").eq("phone", profile["student_id"]).execute()
    if existing.data:
        _client().table("student_profiles").update(row).eq("phone", profile["student_id"]).execute()
    else:
        _client().table("student_profiles").insert(row).execute()


def _sync_save_messages(student_id: str, messages: list):
    _client().table("student_profiles").update({"session_history": messages}).eq("phone", student_id).execute()


async def get_profile(student_id: str):
    return await asyncio.to_thread(_sync_get_profile, student_id)


async def save_profile(profile: dict):
    await asyncio.to_thread(_sync_save_profile, profile)


async def save_messages(student_id: str, messages: list):
    await asyncio.to_thread(_sync_save_messages, student_id, messages)
