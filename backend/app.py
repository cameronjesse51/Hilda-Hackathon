import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

load_dotenv()

from backend.agent.profile import empty_profile
from backend.agent.conversation import run_conversation, stream_conversation
from backend import db

import time
import asyncio
import httpx
from datetime import datetime, timezone

load_dotenv()

app = FastAPI(title="Halda AI College Counselor")

@app.on_event("startup")
async def start_sms_cron():
    asyncio.create_task(sms_cron_job())

async def sms_cron_job():
    while True:
        try:
            now = time.time()
            # 1. Idle Timeout Welcome SMS
            for student_id, profile in profiles.items():
                last_active = profile.get("last_active_at", now)
                phone = profile.get("contact", {}).get("phone")
                
                if (now - last_active > 300) and phone and not profile.get("welcome_sms_sent"):
                    print(f"Sending welcome SMS to {phone}...")
                    
                    try:
                        import anthropic
                        import json
                        claude = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                        sys_prompt = (
                            "You are Halda, an AI college counselor. The student has left the chat. "
                            "Write a casual, 1-to-2 sentence SMS to get them to come back. "
                            "Reference their specific goals, constraints, or stage to prove you were listening. "
                            "End with an invitation to reply. Keep it under 160 characters. "
                            "Do not include quotes or prefixes, just the exact SMS text."
                        )
                        ai_res = await claude.messages.create(
                            model="claude-3-5-sonnet-20241022",
                            max_tokens=100,
                            temperature=0.7,
                            system=sys_prompt,
                            messages=[{"role": "user", "content": f"Student Profile: {json.dumps(profile)}"}]
                        )
                        message_body = ai_res.content[0].text.strip().strip('"')
                    except Exception as e:
                        print(f"Claude SMS generation failed: {e}")
                        message_body = "Hey, it's Halda! Thanks for chatting. Text me back anytime if you have more college questions!"

                    key = os.environ.get("TEXTBELT_KEY", "textbelt")
                    async with httpx.AsyncClient() as client:
                        resp = await client.post('https://textbelt.com/text', data={
                            'phone': phone,
                            'message': message_body,
                            'key': key,
                        })
                        print("Textbelt:", resp.json())
                    profile["welcome_sms_sent"] = True

            # 2. Scheduled Check-ins from DB
            db_now = datetime.now(timezone.utc).isoformat()
            res = supabase.table("scheduled_checkins").select("*").lte("send_at", db_now).is_("sent_at", "null").execute()
            for checkin in res.data or []:
                student_id = checkin["student_id"]
                message_body = checkin["message_body"]
                
                phone = profiles.get(student_id, {}).get("contact", {}).get("phone")
                if phone:
                    print(f"Sending scheduled SMS to {phone}...")
                    key = os.environ.get("TEXTBELT_KEY", "textbelt")
                    async with httpx.AsyncClient() as client:
                        resp = await client.post('https://textbelt.com/text', data={
                            'phone': phone,
                            'message': message_body,
                            'key': key,
                        })
                        print("Textbelt:", resp.json())
                
                # Mark sent
                supabase.table("scheduled_checkins").update({
                    "sent_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", checkin["id"]).execute()

        except Exception as e:
            print("SMS Cron Error:", e)
        
        await asyncio.sleep(60)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import json
from pathlib import Path
schools_path = Path(__file__).parent / "schools.json"
with open(schools_path) as f:
    SCHOOLS_DATA = json.load(f)

profiles: dict[str, dict] = {}
conversations: dict[str, list] = {}

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

GRADE_TO_STAGE = {
    "9th": "sophomore",
    "10th": "sophomore",
    "11th": "junior",
    "12th": "senior",
}


class ChatRequest(BaseModel):
    student_id: str
    message: str


class ChatResponse(BaseModel):
    response: str
    updated_profile: dict


class OnboardRequest(BaseModel):
    student_id: str
    name: str
    grade: str
    zip: str
    high_school: str
    goals: str = ""


def _extract_goals_into_profile(profile: dict, goals: str) -> dict:
    """
    Lightweight pre-extraction: seed stated.interests and stated.career_goals
    from the goals text before the first Claude message, so Claude inherits
    context rather than re-discovering it from scratch.
    """
    if not goals:
        return profile

    goals_lower = goals.lower()

    # Career keyword → career_goals bucket
    career_keywords = [
        "doctor", "nurse", "nursing", "engineer", "engineering", "lawyer", "law",
        "teacher", "teaching", "business", "entrepreneur", "artist", "design",
        "computer", "software", "coding", "programming", "biology", "science",
        "psychology", "social work", "medicine", "research", "military",
        "environmental", "architecture", "music", "film", "media", "finance",
        "accounting", "marketing", "sports", "athlete", "gaming", "animation",
    ]

    # Interest/topic keywords → interests bucket
    interest_keywords = [
        "math", "reading", "writing", "history", "art", "music", "sports",
        "gaming", "technology", "nature", "animals", "travel", "languages",
        "volunteering", "community", "politics", "debate", "drama", "theater",
        "photography", "cooking", "fashion", "coding", "robotics",
    ]

    found_careers = [k for k in career_keywords if k in goals_lower]
    found_interests = [k for k in interest_keywords if k in goals_lower]

    if found_careers:
        existing = set(profile["stated"]["career_goals"])
        for c in found_careers:
            if c not in existing:
                profile["stated"]["career_goals"].append(c)

    if found_interests:
        existing = set(profile["stated"]["interests"])
        for i in found_interests:
            if i not in existing:
                profile["stated"]["interests"].append(i)

    # Transfer detection
    if any(w in goals_lower for w in ["transfer", "community college", "cc ", "already in college"]):
        profile["hard_constraints"]["transfer_student"] = True
        profile["stage"] = "transfer"

    return profile


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    profile = await db.get_profile(req.student_id)
    if not profile:
        profile = empty_profile(req.student_id)

    history = profile.get("session_history", [])

    response_text, updated_profile, updated_history = await run_conversation(
        student_id=req.student_id,
        user_message=req.message,
        profile=profile,
        history=history,
    )

    updated_profile["session_history"] = updated_history
    updated_profile["last_active_at"] = time.time()
    await db.save_profile(updated_profile)
    
    profiles[req.student_id] = updated_profile
    conversations[req.student_id] = updated_history

    return ChatResponse(response=response_text, updated_profile=updated_profile)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    profile = await db.get_profile(req.student_id)
    if not profile:
        profile = empty_profile(req.student_id)

    history = profile.get("session_history", [])

    async def event_generator():
        async for event in stream_conversation(
            student_id=req.student_id,
            user_message=req.message,
            profile=profile,
            history=history,
        ):
            yield event
        profile["session_history"] = history
        profile["last_active_at"] = time.time()
        await db.save_profile(profile)
        
        profiles[req.student_id] = profile
        conversations[req.student_id] = history

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/onboard")
async def onboard(req: OnboardRequest):
    profile = empty_profile(req.student_id)

    parts = req.name.split(None, 1)
    first_name = parts[0]
    profile["contact"]["first_name"] = first_name
    profile["contact"]["last_name"] = parts[1] if len(parts) > 1 else ""
    profile["contact"]["zip"] = req.zip
    profile["contact"]["high_school"] = req.high_school
    profile["academic"]["grade"] = req.grade
    profile["stage"] = GRADE_TO_STAGE.get(req.grade, "sophomore")

    # Pre-extract goals text into the profile before Claude ever sees it
    if req.goals:
        profile = _extract_goals_into_profile(profile, req.goals)
        
    await db.save_profile(profile)

    profiles[req.student_id] = profile

    # Build the first-session internal trigger message Claude will respond to.
    # This is never shown to the student — it primes Claude to open with a
    # stage-appropriate response rather than a blank slate reply.
    stage = profile["stage"]
    stage_context = {
        "sophomore": (
            f"This is {first_name}'s first session. They're a sophomore — early in the process. "
            "Open by making them feel like this is easy, not overwhelming. "
            "Acknowledge what they shared about their interests/goals briefly, then give them "
            "ONE small, concrete thing to think about or do before next time. "
            "End with a hook that makes them want to come back. Do NOT mention specific colleges yet."
        ),
        "junior": (
            f"This is {first_name}'s first session. They're a junior — the process is real now. "
            "Acknowledge their goals, then quickly orient them: what you'll help with (school list, "
            "scholarships, SAT/ACT if needed). Ask one focused follow-up question to start building "
            "their profile. Be direct and energetic — there's real work to do."
        ),
        "senior": (
            f"This is {first_name}'s first session. They're a senior — deadlines are real. "
            "Open with urgency but not panic. Acknowledge their goals, then ask immediately: "
            "have they started applications yet? What schools are they considering? "
            "Be direct. Time matters."
        ),
        "transfer": (
            f"This is {first_name}'s first session. They are a transfer student. "
            "Skip the standard intro. Go straight to credit transfer: ask what credits they have, "
            "where they're transferring from, and what program they want. "
            "Cost and schedule flexibility are likely hard constraints — ask early."
        ),
    }

    first_message = (
        f"[SYSTEM: First session for student {req.student_id}. "
        f"Student just completed onboarding. Their stated goals: \"{req.goals}\". "
        f"{stage_context.get(stage, stage_context['sophomore'])} "
        f"Their pre-extracted profile context is available in the system prompt. "
        f"Call update_profile immediately to refine any inferences from their goals text, "
        f"then deliver your opening response.]"
    )

    # Seed the conversation and get Claude's opening response
    history = []
    response_text, updated_profile, updated_history = await run_conversation(
        student_id=req.student_id,
        user_message=first_message,
        profile=profile,
        history=history,
    )

    profiles[req.student_id] = updated_profile
    conversations[req.student_id] = updated_history

    return {
        "profile": updated_profile,
        "first_message": response_text,
    }


@app.get("/api/schools/search")
async def search_schools(q: str = Query(""), zip: str = Query("")):
    if len(q) < 2:
        if zip:
            result = (
                supabase.table("high_schools")
                .select("*")
                .eq("zip", zip)
                .limit(5)
                .execute()
            )
            return {"schools": result.data or []}
        return {"schools": []}

    result = supabase.rpc(
        "search_high_schools",
        {"query": q, "zip_code": zip},
    ).execute()

    return {"schools": result.data or []}


@app.get("/profile/{student_id}")
async def get_profile(student_id: str):
    profile = await db.get_profile(student_id)
    if not profile:
        return {"error": "Student not found"}
    return profile
