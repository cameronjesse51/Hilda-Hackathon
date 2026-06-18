import os
import hmac
import json

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from supabase import create_client

load_dotenv()

try:
    from backend.agent.conversation import run_conversation, stream_conversation
    from backend.auth import create_session_token, get_current_student, validate_dev_auth_key
    from backend.phone import normalize_phone_e164
    from backend.sms_config import welcome_sms_enabled
    from backend import db
except ModuleNotFoundError:
    from agent.conversation import run_conversation, stream_conversation
    from auth import create_session_token, get_current_student, validate_dev_auth_key
    from phone import normalize_phone_e164
    from sms_config import welcome_sms_enabled
    import db

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
                try:
                    phone = normalize_phone_e164(profile.get("contact", {}).get("phone"))
                except ValueError:
                    phone = None
                
                if (
                    welcome_sms_enabled()
                    and (now - last_active > 300)
                    and phone
                    and not profile.get("welcome_sms_sent")
                ):
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
                student_id = str(checkin["student_id"])
                message_body = checkin["message_body"]

                profile = profiles.get(student_id)
                if not profile:
                    profile = await db.get_profile(student_id)
                try:
                    phone = normalize_phone_e164(
                        (profile or {}).get("contact", {}).get("phone")
                    )
                except ValueError:
                    phone = None
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

profiles: dict[str, dict] = {}
conversations: dict[str, list] = {}

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])

GRADE_TO_STAGE = {
    "9th": "freshman",
    "10th": "sophomore",
    "11th": "junior",
    "12th": "senior"
}


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    updated_profile: dict


class EssayChatRequest(BaseModel):
    message: str
    essay_title: str = ""
    essay_content: str = ""
    history: list = []


class OnboardRequest(BaseModel):
    name: str
    grade: str
    zip: str
    high_school: str
    goals: str = ""


class SessionRequest(BaseModel):
    phone: str


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "api"}


@app.post("/auth/session")
async def issue_session(
    req: SessionRequest,
    x_internal_secret: str = Header(default=""),
):
    expected_secret = os.environ.get("SESSION_SECRET", "")
    if len(expected_secret) < 32 or not hmac.compare_digest(x_internal_secret, expected_secret):
        raise HTTPException(status_code=401, detail="Invalid internal credentials")

    try:
        phone = normalize_phone_e164(req.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    profile = await db.get_or_create_profile(phone)
    token, expires_at = create_session_token(profile["student_id"], phone)
    return {
        "token": token,
        "expires_at": expires_at,
        "student_id": profile["student_id"],
    }


_DEMO_SEED: dict[str, dict] = {
    "+15550000001": {  # Maya — first-gen, nursing, tight budget
        "contact": {"first_name": "Maya", "last_name": "Torres", "zip": "77001", "high_school": "Houston ISD Nursing Magnet (Houston, TX)"},
        "academic": {"grade": "12th", "gpa": 3.4, "intended_major": "Nursing / BSN", "transfer_credits": None},
        "stated": {"interests": ["healthcare", "science", "volunteering", "community"], "career_goals": ["nurse", "nursing", "healthcare"], "location_pref": ["texas", "southeast"], "school_size_pref": "medium"},
        "hard_constraints": {"max_cost": 15000, "transfer_student": False, "visa_required": False},
        "stage": "senior",
        "session_history": [
            {"role": "user", "content": "Hi, I want to be a nurse. My family can't pay more than $15,000 a year for college. I'm the first in my family to go."},
            {"role": "assistant", "content": "Hi Maya! Nursing is a really meaningful path, and $15K/year is workable — especially with federal aid and the right school choices. Since you're the first in your family to go through this, I want to make sure nothing falls through the cracks. A few nursing-specific scholarships are actually set aside for first-gen students. Are you an in-state Texas resident? That's going to open up some strong affordable BSN programs we should look at first."},
        ],
    },
    "+15550000002": {  # Caleb — high achiever, CS, wants data
        "contact": {"first_name": "Caleb", "last_name": "Park", "zip": "10001", "high_school": "Stuyvesant High School (New York, NY)"},
        "academic": {"grade": "12th", "gpa": 3.9, "intended_major": "Computer Science", "transfer_credits": None},
        "stated": {"interests": ["coding", "math", "algorithms", "research"], "career_goals": ["software engineering", "research", "technology"], "location_pref": [], "school_size_pref": "large"},
        "hard_constraints": {"max_cost": 32000, "transfer_student": False, "visa_required": False},
        "stage": "senior",
        "session_history": [
            {"role": "user", "content": "I have a 3.9 GPA and I want to study CS. I'm comparing MIT, Carnegie Mellon, Stanford, Georgia Tech, UIUC, and UT Austin. Give me the real data, not the hype."},
            {"role": "assistant", "content": "Straight data, no hype — I respect that. Acceptance rates for CS specifically: MIT ~4%, Stanford ~4%, CMU School of Computer Science ~7% (most selective CS program in the country), Georgia Tech ~17% overall but CS is impacted, UIUC CS ~16% for in-state / lower for out-of-state, UT Austin CS ~8% into the major directly. Post-grad median salary within 2 years: all six land $130K–$165K depending on role. What metric matters most for your decision — research output, industry placement, or cost?"},
        ],
    },
    "+15550000003": {  # Rosa — transfer, working full-time, credits first
        "contact": {"first_name": "Rosa", "last_name": "Mendez", "zip": "85201", "high_school": "Mesa Community College (Mesa, AZ)"},
        "academic": {"grade": "transfer", "gpa": 3.7, "intended_major": "Business Administration", "transfer_credits": 45},
        "stated": {"interests": ["business", "management", "community"], "career_goals": ["business", "management"], "location_pref": ["arizona", "southwest"], "school_size_pref": "medium"},
        "hard_constraints": {"max_cost": 20000, "transfer_student": True, "commuter": True, "visa_required": False},
        "stage": "transfer",
        "session_history": [
            {"role": "user", "content": "I'm 24, at Mesa Community College, working full-time. I have about 45 credits done. I need to know if my credits will transfer before I think about anything else."},
            {"role": "assistant", "content": "Completely fair — credit transfer has to come first. 45 credits is significant and you need to protect every one. The clearest path in Arizona is ASU, which has formal transfer articulation agreements with MCC through AZTransfer.gov. Are most of your credits general education (English, math, social science) or do you have business-specific courses? That changes which programs will accept the most credits and whether you can enter as a junior."},
        ],
    },
    "+15550000004": {  # Devon — career-first, environmental science, no school intent yet
        "contact": {"first_name": "Devon", "last_name": "Reyes", "zip": "97201", "high_school": "Portland High School (Portland, OR)"},
        "academic": {"grade": "10th", "gpa": 3.5, "intended_major": "", "transfer_credits": None},
        "stated": {"interests": ["environment", "science", "nature", "outdoors"], "career_goals": [], "location_pref": [], "school_size_pref": ""},
        "hard_constraints": {"max_cost": None, "transfer_student": False, "visa_required": False},
        "stage": "sophomore",
        "session_history": [
            {"role": "user", "content": "I like environmental science but I don't know if it's actually a real career. My parents keep saying I should pick something more practical."},
            {"role": "assistant", "content": "That's worth taking seriously — and I'll give you a real answer instead of just telling you to follow your passion. Environmental science branches into a lot of directions: environmental consulting (steady corporate work), EPA and government roles (structured, stable), clean energy and sustainability (growing fast right now), nonprofit advocacy, and research (usually needs grad school). Before we talk about schools at all, I want to figure out which of those directions actually fits how you think. Can I ask you a couple of quick questions — not about school, just about how you approach problems?"},
        ],
    },
    "+15550000005": {  # Anika — international, India, visa, CS, scholarships
        "contact": {"first_name": "Anika", "last_name": "Sharma", "zip": "", "high_school": "Delhi Public School (New Delhi, India)"},
        "academic": {"grade": "12th", "gpa": 3.8, "intended_major": "Computer Science", "transfer_credits": None},
        "stated": {"interests": ["coding", "technology", "math", "AI"], "career_goals": ["software engineering", "technology"], "location_pref": ["northeast", "west coast"], "school_size_pref": "large"},
        "hard_constraints": {"max_cost": 32000, "transfer_student": False, "visa_required": True},
        "stage": "senior",
        "session_history": [
            {"role": "user", "content": "I'm applying from India. I need a university with a strong CS program that accepts international students and has scholarships for internationals. I need an F-1 visa."},
            {"role": "assistant", "content": "Got it — I'll filter specifically for international-student-friendly programs. A few things I'll prioritize: schools with high international student populations (better support systems and OPT track record), CS programs with strong STEM OPT extension history (critical for post-graduation work auth), and schools that actually fund international students rather than just accepting them. Merit scholarships for internationals are rarer but they exist — Carnegie Mellon, University of Rochester, and Case Western are known for them. Do you have a budget ceiling for annual tuition plus living costs, and are you flexible on location within the US?"},
        ],
    },
    "+15550000006": {  # Jordan — sophomore, blank slate, just needs a reason to return
        "contact": {"first_name": "Jordan", "last_name": "Williams", "zip": "84101", "high_school": "Salt Lake City High School (Salt Lake City, UT)"},
        "academic": {"grade": "10th", "gpa": 3.2, "intended_major": "", "transfer_credits": None},
        "stated": {"interests": [], "career_goals": [], "location_pref": [], "school_size_pref": ""},
        "hard_constraints": {"max_cost": None, "transfer_student": False, "visa_required": False},
        "stage": "sophomore",
        "session_history": [
            {"role": "user", "content": "My mom made me do this. I'm a sophomore and I honestly don't know anything about college yet."},
            {"role": "assistant", "content": "Ha — fair enough, I'll take it. Honestly, sophomore year is the best time to start because nothing you do now is permanent and there's no pressure to have it figured out. Most of what we'll do is just get a sense of who you are — schools come way later. One question, no wrong answer: is there anything you've done in the last year — a class, a project, anything — that didn't feel like a waste of your time?"},
        ],
    },
}


def _seed_demo_profile(profile: dict, phone: str) -> dict:
    seed = _DEMO_SEED.get(phone)
    if not seed:
        return profile
    c = seed["contact"]
    profile["contact"].update({"first_name": c["first_name"], "last_name": c["last_name"], "zip": c["zip"], "high_school": c["high_school"]})
    a = seed["academic"]
    profile["academic"].update({"grade": a["grade"], "gpa": a["gpa"], "intended_major": a["intended_major"], "transfer_credits": a["transfer_credits"]})
    s = seed["stated"]
    profile["stated"].update({"interests": s["interests"], "career_goals": s["career_goals"], "location_pref": s["location_pref"], "school_size_pref": s["school_size_pref"]})
    h = seed["hard_constraints"]
    profile["hard_constraints"].update({"max_cost": h["max_cost"], "transfer_student": h["transfer_student"]})
    profile["stage"] = seed["stage"]
    profile["session_history"] = seed["session_history"]
    return profile


@app.post("/auth/dev-session")
async def issue_dev_session(
    x_dev_auth_key: str = Header(default=""),
    x_demo_phone: str = Header(default=""),
):
    phone = validate_dev_auth_key(x_dev_auth_key, demo_phone=x_demo_phone or None)
    profile = await db.get_or_create_profile(phone)

    if x_demo_phone and not profile.get("contact", {}).get("first_name"):
        profile = _seed_demo_profile(profile, phone)
        await db.save_profile(profile)

    token, expires_at = create_session_token(profile["student_id"], phone)
    return {
        "token": token,
        "expires_at": expires_at,
        "student_id": profile["student_id"],
    }


@app.post("/auth/demo-session")
async def issue_demo_session(x_demo_phone: str = Header(default="")):
    """Keyless endpoint for judge/demo personas — no dev key required."""
    if not x_demo_phone:
        raise HTTPException(status_code=400, detail="X-Demo-Phone header is required")
    allowed = {
        p.strip()
        for p in os.environ.get("DEMO_PERSONA_PHONES", "").split(",")
        if p.strip()
    }
    if not allowed:
        raise HTTPException(status_code=503, detail="Demo personas are not configured")
    try:
        phone = normalize_phone_e164(x_demo_phone)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid phone number")
    if phone not in allowed:
        raise HTTPException(status_code=403, detail="Demo persona not found")

    try:
        profile = await db.get_or_create_profile(phone)
        if not profile.get("contact", {}).get("first_name"):
            profile = _seed_demo_profile(profile, phone)
            await db.save_profile(profile)
        token, expires_at = create_session_token(profile["student_id"], phone)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Demo login failed: {exc}")

    return {
        "token": token,
        "expires_at": expires_at,
        "student_id": profile["student_id"],
    }


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
async def chat(req: ChatRequest, student_id: str = Depends(get_current_student)):
    profile = await db.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    history = profile.get("session_history", [])

    response_text, updated_profile, updated_history = await run_conversation(
        student_id=student_id,
        user_message=req.message,
        profile=profile,
        history=history,
    )

    updated_profile["session_history"] = updated_history
    updated_profile["last_active_at"] = time.time()
    await db.save_profile(updated_profile)
    
    profiles[student_id] = updated_profile
    conversations[student_id] = updated_history

    return ChatResponse(response=response_text, updated_profile=updated_profile)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, student_id: str = Depends(get_current_student)):
    profile = await db.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")

    history = profile.get("session_history", [])

    async def event_generator():
        async for event in stream_conversation(
            student_id=student_id,
            user_message=req.message,
            profile=profile,
            history=history,
        ):
            yield event
        profile["session_history"] = history
        profile["last_active_at"] = time.time()
        await db.save_profile(profile)
        
        profiles[student_id] = profile
        conversations[student_id] = history

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/essay/chat/stream")
async def essay_chat_stream(req: EssayChatRequest, student_id: str = Depends(get_current_student)):
    import anthropic

    essay_context = ""
    if req.essay_title or req.essay_content:
        essay_context = (
            f'\n\nThe student\'s current essay (titled "{req.essay_title or "Untitled"}"):\n'
            f'"""\n{req.essay_content}\n"""'
        )

    system_prompt = (
        "You are Halda, an AI college counselor and essay writing coach. "
        "You help students craft compelling college application essays. "
        "Be specific, encouraging, and give actionable feedback. "
        "When the student's essay is provided, reference their actual text when giving feedback. "
        "Keep responses focused and conversational — this is a real-time chat."
        + essay_context
    )

    messages = []
    for item in req.history:
        role = item.get("role", "user") if isinstance(item, dict) else "user"
        content = item.get("content", "") if isinstance(item, dict) else ""
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Claude requires conversations to start with a user turn
    while messages and messages[0]["role"] == "assistant":
        messages.pop(0)

    messages.append({"role": "user", "content": req.message})

    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    async def generate():
        async with client.messages.stream(
            model="claude-opus-4-8",
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"event: text_delta\ndata: {json.dumps({'text': text})}\n\n"
        yield f"event: done\ndata: {{}}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _prepare_onboarding(req: OnboardRequest, profile: dict) -> tuple[dict, str]:
    student_id = profile["student_id"]

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
        
    # Build the first-session internal trigger message Claude will respond to.
    # This is never shown to the student — it primes Claude to open with a
    # stage-appropriate response rather than a blank slate reply.
    stage = profile["stage"]
    stage_context = {
        "sophomore": (
            f"This is {first_name}'s first session. They're a sophomore — early in the process. "
            "Open by making them feel like this is easy, not overwhelming. "
            "Acknowledge what they shared about their interests/goals and respond to the request "
            "they made. If they explicitly requested college recommendations, search, or comparison, "
            "call search_colleges now and give them the results. Otherwise, offer one useful next step "
            "and keep the conversation open naturally."
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
        f"[SYSTEM: First session for student {student_id}. "
        f"Student just completed onboarding. Their stated goals: \"{req.goals}\". "
        f"{stage_context.get(stage, stage_context['sophomore'])} "
        f"Treat the stated goals as the student's latest explicit message. Fulfill any direct "
        f"request in those goals during this response; do not postpone it until a later turn. "
        f"Their pre-extracted profile context is available in the system prompt. "
        f"Call update_profile immediately to refine any inferences from their goals text, "
        f"then deliver your opening response.]"
    )

    return profile, first_message


@app.post("/api/onboard")
async def onboard(req: OnboardRequest, student_id: str = Depends(get_current_student)):
    profile = await db.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    if profile.get("contact", {}).get("first_name"):
        raise HTTPException(status_code=409, detail="Student is already onboarded")
    profile, first_message = _prepare_onboarding(req, profile)

    await db.save_profile(profile)
    profiles[student_id] = profile

    # Seed the conversation and get Claude's opening response
    history = []
    response_text, updated_profile, updated_history = await run_conversation(
        student_id=student_id,
        user_message=first_message,
        profile=profile,
        history=history,
    )

    updated_profile["session_history"] = updated_history
    updated_profile["last_active_at"] = time.time()
    await db.save_profile(updated_profile)

    profiles[student_id] = updated_profile
    conversations[student_id] = updated_history

    return {
        "profile": updated_profile,
        "first_message": response_text,
    }


@app.post("/api/onboard/stream")
async def onboard_stream(req: OnboardRequest, student_id: str = Depends(get_current_student)):
    profile = await db.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    if profile.get("contact", {}).get("first_name"):
        raise HTTPException(status_code=409, detail="Student is already onboarded")
    profile, first_message = _prepare_onboarding(req, profile)

    await db.save_profile(profile)
    profiles[student_id] = profile
    history = []

    async def event_generator():
        async for event in stream_conversation(
            student_id=student_id,
            user_message=first_message,
            profile=profile,
            history=history,
        ):
            yield event

        profile["session_history"] = history
        profile["last_active_at"] = time.time()
        await db.save_profile(profile)

        profiles[student_id] = profile
        conversations[student_id] = history

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


@app.get("/profile/me")
async def get_profile(student_id: str = Depends(get_current_student)):
    profile = await db.get_profile(student_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    return profile


@app.get("/api/recommendations")
async def list_recommendations(
    limit: int = Query(10, ge=1, le=50),
    student_id: str = Depends(get_current_student),
):
    recommendation_sets = await db.list_recommendation_sets(student_id, limit)
    return {"recommendation_sets": recommendation_sets}


@app.get("/api/recommendations/{recommendation_set_id}")
async def get_recommendation(
    recommendation_set_id: str,
    student_id: str = Depends(get_current_student),
):
    recommendation_set = await db.get_recommendation_set(
        student_id,
        recommendation_set_id,
    )
    if not recommendation_set:
        raise HTTPException(status_code=404, detail="Recommendation set not found")
    return recommendation_set
