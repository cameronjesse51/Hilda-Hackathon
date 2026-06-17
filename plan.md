# HALDA AI COLLEGE COUNSELOR — HACKATHON BUILD HANDOFF

You are helping build a winning hackathon submission for the HITLAB World Cup 2026, Track 2 at Utah Valley University. This is a 24-hour build window with a $10K prize. The submission is judged 40% student experience, 35% technical execution, 25% creativity.

## What we are building

An always-on AI college counselor called Halda that meets students where they are (web chat, SMS, email) and builds a rich profile over time. Free for students. Schools purchase matched student profiles as leads. The core value prop: most tools ask students what they want. Halda figures out who they actually are through conversation, probing, and behavioral signals — then matches them to the right school.

## Hard requirements from the brief

- Multi-channel with distinct purposes: **web is the rich experience** (chat + profile side panel + college cards + micro-internship UI), **SMS is the retention channel** that keeps students engaged after they close the browser. SMS is not a second chat interface — it's how Halda nudges students back via scheduled check-ins, deadline reminders, and follow-ups triggered by `schedule_checkin`. The flow is: discover and explore on web → stay connected over SMS.
- Real college data pulled from the College Scorecard API (https://collegescorecard.ed.gov/data/documentation/) — no mocked college data in the demo
- Student accounts with fully isolated multi-tenant architecture — no shared state between students
- Profile builds progressively across sessions — every conversation adds signal
- Live working demo on Thursday, judges will interact directly

## The six test personas — the demo must feel meaningfully different for each

These are the judge's test cases. If two feel the same, the agent is not personalizing enough.

- **Maya, 17, first-gen** — wants nursing, family can't pay more than $15K/year, needs the agent to lead her
- **Caleb, 18, high achiever** — 3.9 GPA, wants CS at a top-20 school, comparing 6 schools, wants data not encouragement
- **Rosa, 24, transfer** — community college, working full-time, needs credit transfer info before anything else
- **Devon, 16, career-first** — interested in environmental science but unsure if it's a real career, agent must lead with career exploration before ever mentioning schools
- **Anika, 17, international** — applying from India, needs visa-friendly schools, strong CS programs, international scholarships
- **Jordan, 15, sophomore** — complete blank slate, needs a reason to come back next month, agent should make the process feel non-overwhelming

## The student profile schema

This is the central data object everything reads from and writes to:

```json
{
  "student_id": "",
  "contact": {
    "first_name": "", "last_name": "", "email": "",
    "phone": "", "zip": "", "high_school": ""
  },
  "academic": {
    "grade": "", "gpa": null, "test_scores": {},
    "intended_major": "", "transfer_credits": null
  },
  "stated": {
    "interests": [], "career_goals": [],
    "location_pref": [], "school_size_pref": ""
  },
  "inferred": {
    "learning_style": "", "risk_tolerance": "",
    "collaboration_pref": "", "ambiguity_tolerance": ""
  },
  "behavioral": {
    "probe_responses": [],
    "micro_internship_results": [],
    "velocity_signals": {
      "causal_reasoning": null,
      "quantitative": null,
      "ambiguity_tolerance": null
    },
    "domain_affinities": {}
  },
  "hard_constraints": {
    "max_cost": null,
    "visa_required": false,
    "transfer_student": false,
    "commuter": false
  },
  "confidence_scores": {
    "career_clarity": 0.0,
    "major_fit": 0.0,
    "culture_fit": 0.0,
    "financial_fit": 0.0
  },
  "stage": "sophomore|junior|senior|transfer",
  "session_history": []
}
```

## The agent architecture

The agent uses Claude claude-sonnet-4-6 via the Anthropic API with tool calling. It does not ask direct survey questions — it extracts profile data naturally from conversation using a background extraction tool that fires after each message. The agent has the following tools:

- `update_profile(fields)` — updates any profile fields from conversation inference
- `probe_concept(domain, concept)` — fires an intuition probe question when a profile dimension has low confidence
- `search_colleges(filters)` — queries College Scorecard API with semantic + hard constraint filtering
- `schedule_checkin(date, topic)` — books a future SMS or email touchpoint
- `handoff_to_sms(phone)` — triggers Twilio SMS when phone number is captured

Every session starts by injecting the full current student profile into the system prompt so the agent always remembers everything.

## The micro-internship and probing system (our creativity differentiator)

Rather than asking students what they want (unreliable), we measure learning velocity and intuition across domains. This is our biggest differentiator and goes directly to the 25% creativity score.

Each micro-internship has 3 modules of increasing complexity (0.3 → 0.6 → 0.9 difficulty). During each module the agent fires interaction prompts of four types:

- `intuition_probe` — ask before teaching to get baseline
- `comprehension_check` — ask right after explaining
- `retention_check` — same concept, different framing, asked later
- `transfer_probe` — can they apply the concept somewhere new

The score delta across these four types per concept is the learning velocity signal. Store it as:

```json
{
  "internship_id": "",
  "domain": "",
  "modules_completed": 0,
  "concept_scores": {},
  "velocity_per_concept": {},
  "overall_domain_velocity": null,
  "acceleration": "positive|plateau|negative",
  "strongest_concept_type": "",
  "inferred_traits": []
}
```

Devon (career-first) is the primary demo vehicle for this feature. Start the micro-internship flow when a student expresses career curiosity but has no school intent.

## The college matching logic

Hybrid search: semantic similarity for fit + hard constraint metadata filtering. Use Qdrant for vector search. Enrich ~20 schools with hand-written culture/vibe fields stored locally. Hard data (cost, programs, outcomes, acceptance rate) comes live from College Scorecard API. The match should explain *why* — surfacing which profile signals drove each recommendation.

The agent triggers college search proactively when `confidence_scores.career_clarity > 0.6` AND `confidence_scores.major_fit > 0.5`. Before that threshold it keeps building the profile.

## The stage-aware experience

The agent behavior changes based on student stage:

- **Sophomore (Jordan)** — career exploration, milestone checklist, reason to return. Never pressure about schools.
- **Junior** — deep school comparison, scholarship discovery, SAT/ACT reminders
- **Senior** — essay coaching, deadline tracking, application support, offer comparison
- **Transfer (Rosa)** — credit transfer first, then everything else. Skip the sophomore/junior flow entirely.

## The demo flow for judges (8 minutes)

1. Open as Jordan (blank slate sophomore) — show onboarding, probing, and the "here's what you should do this year" milestone output. Show the reason-to-return hook.
2. Switch to Devon — trigger the career exploration micro-internship for environmental science. Show learning velocity being captured and career clarity score increasing.
3. Switch to Caleb — run a real College Scorecard query for top CS programs filtered by acceptance rate and outcomes. Show real data returned and explained.
4. **The SMS moment** — during one of the above demos, capture a phone number. Then have the judge receive a live Twilio text on their own phone from Halda — a scheduled check-in, a deadline reminder, or a follow-up on something discussed in the web chat. This is the visceral proof that Halda stays in the student's life after they close the tab.

## Tech stack

- **Frontend:** React web chat UI
- **Backend:** Node.js or Python FastAPI
- **Database:** Supabase (student profiles, session history, multi-tenant isolation)
- **Vector DB:** Qdrant (college embeddings for semantic search)
- **LLM:** Claude claude-sonnet-4-6 via Anthropic API with tool calling
- **SMS:** Twilio
- **College data:** College Scorecard API (real, live)
- **Hosting:** Whatever deploys fastest — Vercel for frontend, Railway or Render for backend

## Team ownership

### AI Engineering (Drew)

1. **Agent core** — system prompt, Claude API conversation loop, tool definitions
2. **Profile extraction** — background inference that turns conversation into profile updates without survey questions
3. **Stage-aware routing** — agent behaves differently for sophomore/senior/transfer/etc.
4. **Micro-internship engine** — probe flow, four probe types, learning velocity scoring
5. **College matching orchestration** — when to trigger search, how to build the query from profile, "here's why" explanations
6. **`schedule_checkin` tool handler** — writes a scheduled event (timestamp, student_id, message/topic) to Supabase. Does NOT send the SMS itself — a backend job/cron picks up due rows and fires Twilio. Your tool just creates the row.

### Data & Backend Infrastructure (Simon)

1. **Supabase schema** — student profiles table matching the profile schema above, with RLS policies for multi-tenant isolation (each student only sees their own data)
2. **`scheduled_checkins` table** — columns: student_id, send_at, channel (sms/email), topic, message_body, sent_at (null until delivered). Drew's `schedule_checkin` tool writes rows here.
3. **`session_history` table** — conversation logs tied to student_id, append-only
4. **College Scorecard API wrapper** — Python functions that query the API with filters Drew's agent needs: cost (avg_net_price), programs offered, acceptance rate, graduation rate, earnings outcomes, visa-friendliness (international student %). Expose clean function signatures Drew can call from his tool handlers.
5. **Qdrant setup** — collection with ~20 seeded college embeddings. Each vector includes metadata fields for hard filtering (net_price, acceptance_rate, programs list, location, school_size). Hand-write culture/vibe text for each school to embed alongside the factual data.
6. **Cron/job runner for scheduled check-ins** — polls `scheduled_checkins` for rows where `send_at <= now()` and `sent_at IS NULL`, fires Twilio SMS, marks row as sent. Simple loop on a timer or a Supabase Edge Function.
7. **Database helper functions** — read/write profile, append session history, read scheduled check-ins. These are the functions Drew stubs against until they're ready.

### Frontend, SMS & Student Experience (Jesse)

1. **React web chat UI** — the primary interface. Chat panel on the left, student profile building live on a side panel on the right. Students see their profile take shape as they talk.
2. **Profile side panel** — renders the student profile in real time as Drew's agent updates it. Show confidence scores as progress bars, interests as tags, hard constraints as a summary card. This is what makes the demo visually compelling — judges see the AI thinking.
3. **College recommendation cards** — when Drew's agent returns college matches, render them as rich cards (school name, cost, acceptance rate, match reasons, key stats). Not just text in the chat.
4. **Micro-internship UI** — when Drew's agent triggers a micro-internship, the probe questions need to feel interactive, not like a quiz. Consider cards, progress indicators, or a distinct visual mode so it feels like a different experience from regular chat.
5. **API integration** — call Drew's FastAPI endpoint with `{student_id, message}`, receive `{response, updated_profile}`, update both chat and side panel. Handle streaming if Drew implements it.
6. **Twilio SMS integration** — set up the Twilio account, phone number, and webhook. When Simon's cron job fires a scheduled check-in, the SMS goes out through Twilio. Also handle the case where a student texts back — route inbound SMS to Drew's conversation loop with the same student_id.
7. **Auth & onboarding flow** — simple student account creation (name + email minimum). Generate student_id, create the profile in Supabase via Simon's helpers. The first chat message should feel like meeting a counselor, not filling out a form.
8. **Deployment** — Vercel for the React frontend, Railway or Render for Drew's FastAPI backend. Get a shareable URL live for the demo.
9. **Demo polish** — pre-seed the three demo personas (Jordan, Devon, Caleb) so judges can switch between them instantly. Make the persona switch seamless — a dropdown or tabs, not separate logins.
10. **The SMS demo moment** — during the live demo, capture a judge's phone number in the web chat. Trigger a live Twilio text to their phone. This is the most memorable beat of the 8-minute demo — make sure it works flawlessly.

### Cross-team dependencies

| Drew needs | From whom | What exactly |
|------------|-----------|--------------|
| Profile read/write functions | Simon | Function signatures for loading and saving student profiles to Supabase |
| `scheduled_checkins` table | Simon | Table ready so `schedule_checkin` tool can write rows |
| College Scorecard wrapper | Simon | Function that takes filters, returns college data |
| Qdrant query interface | Simon | Function that takes an embedding + metadata filters, returns matched colleges |
| API contract | Jesse | Agreement on `{student_id, message}` → `{response, updated_profile}` shape |
| Inbound SMS routing | Jesse | Twilio webhook that forwards incoming texts to Drew's conversation loop |

| Simon needs | From whom | What exactly |
|-------------|-----------|--------------|
| Profile schema finalized | Drew | Confirm the JSON schema is the final shape so tables can be built |
| College filter list | Drew | Exact fields the agent will filter on so the wrapper and Qdrant metadata match |

| Jesse needs | From whom | What exactly |
|-------------|-----------|--------------|
| API endpoint live | Drew | FastAPI route accepting requests so frontend can integrate |
| Profile update format | Drew | Shape of the `updated_profile` in the response so the side panel knows what to render |
| Scheduled check-in delivery | Simon | Cron job working so SMS demo moment is reliable |

## Scaffolding order (Drew)

1. **System prompt + tool schemas** — write the Claude tool_use JSON schemas for all five tools, write the system prompt with profile injection slot. Zero dependencies, start now.
2. **Conversation loop endpoint** — FastAPI route: takes student_id + message, loads profile (stub with a dict), calls Claude, parses tool calls, returns response. This is the integration surface everyone plugs into.
3. **`update_profile` handler** — Claude calls it with inferred fields, you validate and merge. Stub the DB write until Simon has Supabase ready.
4. **`search_colleges` handler** — stub it to call Simon's wrapper. Hardcoded filters first, swap to profile-driven once extraction works.
5. **Micro-internship state machine** — probe flow with difficulty escalation and velocity scoring. Self-contained, mostly prompt engineering + a scoring function.
6. **`schedule_checkin` handler** — writes a row to `scheduled_checkins` in Supabase (student_id, send_at timestamp, channel, message/topic). Simon's cron job picks up due rows and fires Twilio.

## The north star for every decision

The brief says "nobody has built a compelling reason for a 10th grader to start early, stay engaged, and actually enjoy the process." Every feature decision should be evaluated against that. If it doesn't make Jordan want to come back next month or make Maya feel like someone is actually in her corner, deprioritize it.
