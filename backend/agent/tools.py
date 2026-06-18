TOOLS = [
    {
        "name": "update_profile",
        "description": (
            "Update the student's profile with information inferred from the conversation. "
            "Call this after every student message to capture any new signals — never ask "
            "the student to fill out a form. Extract naturally from what they say."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "contact": {
                    "type": "object",
                    "description": "Contact info gleaned from conversation",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "zip": {"type": "string"},
                        "high_school": {"type": "string"},
                    },
                },
                "academic": {
                    "type": "object",
                    "description": "Academic details mentioned or implied",
                    "properties": {
                        "grade": {"type": "string", "enum": ["9", "10", "11", "12", "college", "graduated"]},
                        "gpa": {"type": "number"},
                        "test_scores": {
                            "type": "object",
                            "description": "e.g. {\"SAT\": 1400, \"ACT\": 32}",
                        },
                        "intended_major": {"type": "string"},
                        "transfer_credits": {"type": "integer"},
                    },
                },
                "stated": {
                    "type": "object",
                    "description": "Things the student explicitly said they want",
                    "properties": {
                        "interests": {"type": "array", "items": {"type": "string"}},
                        "career_goals": {"type": "array", "items": {"type": "string"}},
                        "location_pref": {"type": "array", "items": {"type": "string"}},
                        "school_size_pref": {
                            "type": "string",
                            "enum": ["small", "medium", "large", "no_preference"],
                        },
                    },
                },
                "inferred": {
                    "type": "object",
                    "description": "Traits you infer from HOW they talk, not what they say",
                    "properties": {
                        "learning_style": {"type": "string"},
                        "risk_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
                        "collaboration_pref": {"type": "string", "enum": ["solo", "collaborative", "mixed"]},
                        "ambiguity_tolerance": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
                "hard_constraints": {
                    "type": "object",
                    "description": "Non-negotiable requirements",
                    "properties": {
                        "max_cost": {"type": "integer", "description": "Max annual cost in USD"},
                        "visa_required": {"type": "boolean"},
                        "transfer_student": {"type": "boolean"},
                        "commuter": {"type": "boolean"},
                    },
                },
                "confidence_scores": {
                    "type": "object",
                    "description": "Your confidence in each dimension, 0.0 to 1.0",
                    "properties": {
                        "career_clarity": {"type": "number"},
                        "major_fit": {"type": "number"},
                        "culture_fit": {"type": "number"},
                        "financial_fit": {"type": "number"},
                    },
                },
                "stage": {
                    "type": "string",
                    "enum": ["sophomore", "junior", "senior", "transfer"],
                    "description": "The student's current stage in the college process",
                },
            },
            "required": [],
        },
    },
    {
        "name": "probe_concept",
        "description": (
            "Fire an intuition probe when a profile dimension has low confidence. "
            "Use this to measure the student's natural reasoning about a domain "
            "before giving them information. Do NOT use this as a quiz — frame it "
            "as a genuine conversation starter. Call this when career_clarity < 0.4 "
            "or major_fit < 0.3 and the student seems open to exploring."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The broad domain to probe, e.g. 'environmental_science', 'computer_science', 'healthcare'",
                },
                "concept": {
                    "type": "string",
                    "description": "The specific concept to probe within the domain",
                },
                "probe_type": {
                    "type": "string",
                    "enum": ["intuition_probe", "comprehension_check", "retention_check", "transfer_probe"],
                    "description": (
                        "intuition_probe: ask before teaching to get baseline. "
                        "comprehension_check: ask right after explaining. "
                        "retention_check: same concept, different framing, asked later. "
                        "transfer_probe: can they apply the concept somewhere new."
                    ),
                },
                "difficulty": {
                    "type": "number",
                    "description": "Difficulty level from 0.0 to 1.0. Start at 0.3, escalate to 0.6, then 0.9.",
                },
            },
            "required": ["domain", "concept", "probe_type", "difficulty"],
        },
    },
    {
        "name": "search_colleges",
        "description": (
            "Search for colleges that match the student's profile. Call this immediately "
            "when the student explicitly asks for college recommendations, a search, or a "
            "comparison, regardless of confidence scores. For proactive searches that the "
            "student did not request, require confidence_scores.career_clarity > 0.6 AND "
            "confidence_scores.major_fit > 0.5. "
            "When you return results, explain WHY each school matches — cite which "
            "profile signals drove the recommendation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language description of what the student is looking for, used for semantic search",
                },
                "filters": {
                    "type": "object",
                    "description": "Hard constraint filters applied alongside semantic search",
                    "properties": {
                        "max_net_price": {"type": "integer", "description": "Maximum annual net price in USD"},
                        "min_acceptance_rate": {"type": "number", "description": "Minimum acceptance rate (0.0-1.0)"},
                        "max_acceptance_rate": {"type": "number", "description": "Maximum acceptance rate (0.0-1.0)"},
                        "programs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required program/major names",
                        },
                        "school_size": {
                            "type": "string",
                            "enum": ["small", "medium", "large"],
                            "description": "small: <5000, medium: 5000-15000, large: >15000",
                        },
                        "visa_friendly": {"type": "boolean", "description": "Filter to schools with >5% international students"},
                        "location_state": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "US state abbreviations to filter by",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of results to return, default 5",
                },
                "comparison_requested": {
                    "type": "boolean",
                    "description": (
                        "Set true when the student explicitly asks to compare the returned "
                        "schools side by side. The client will open the comparison automatically."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "schedule_checkin",
        "description": (
            "Schedule a future check-in with the student via SMS or email. "
            "Use this to keep students engaged — especially sophomores who need "
            "a reason to come back. Write the row to the database; a separate "
            "backend job handles actual delivery. Good triggers: deadline reminders, "
            "follow-ups on topics discussed, milestone nudges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["sms", "email"],
                    "description": "Delivery channel. Use SMS if phone is captured, otherwise email.",
                },
                "send_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime for when to send, e.g. '2026-07-15T10:00:00Z'",
                },
                "topic": {
                    "type": "string",
                    "description": "Short label for the check-in, e.g. 'scholarship_deadline_reminder'",
                },
                "message_body": {
                    "type": "string",
                    "description": "The actual message to send. Keep it warm, personal, and under 160 chars for SMS.",
                },
            },
            "required": ["channel", "send_at", "topic", "message_body"],
        },
    },
    {
        "name": "search_scholarships",
        "description": (
            "Search the web for scholarships and grants that match the student's profile. "
            "Call this when the student asks about scholarships, grants, financial aid, or "
            "'money for college'. Also call proactively for juniors and seniors when a "
            "financial constraint (hard_constraints.max_cost) is known. "
            "Always return results with source links so the student can apply directly. "
            "Do NOT fabricate scholarship names, amounts, or deadlines."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language description of what to search for, enriched with "
                        "profile signals. E.g. 'first-generation college student scholarships "
                        "for nursing majors in Texas 2026'"
                    ),
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters to narrow the search",
                    "properties": {
                        "major": {
                            "type": "string",
                            "description": "Intended major or field of study",
                        },
                        "state": {
                            "type": "string",
                            "description": "US state abbreviation or full name to focus on state-specific awards",
                        },
                        "gpa_min": {
                            "type": "number",
                            "description": "Minimum GPA required for eligibility",
                        },
                        "ethnicity": {
                            "type": "string",
                            "description": "Ethnicity-specific scholarships if the student has expressed this preference",
                        },
                        "need_based": {
                            "type": "boolean",
                            "description": "Set true to prioritize need-based awards",
                        },
                        "merit_based": {
                            "type": "boolean",
                            "description": "Set true to prioritize merit-based awards",
                        },
                        "deadline_within_days": {
                            "type": "integer",
                            "description": "Return only scholarships with deadlines within this many days",
                        },
                        "amount_min": {
                            "type": "integer",
                            "description": "Minimum award amount in USD",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of results to return (default 5, max 10)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "score_probe_response",
        "description": (
            "Score a student's response to a micro-internship probe question. "
            "Call this AFTER the student answers a probe. Score based on reasoning "
            "quality and depth of thinking, NOT correctness. A student who reasons "
            "well but gets the wrong answer scores higher than one who guesses right. "
            "0.0 = no engagement, 0.5 = reasonable attempt, 1.0 = exceptional reasoning."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain being probed, e.g. 'environmental_science'",
                },
                "concept": {
                    "type": "string",
                    "description": "The concept being probed, e.g. 'ecosystems'",
                },
                "probe_type": {
                    "type": "string",
                    "enum": ["intuition_probe", "comprehension_check", "retention_check", "transfer_probe"],
                },
                "score": {
                    "type": "number",
                    "description": "Score from 0.0 to 1.0 based on reasoning quality",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief note on what the score reflects about the student's thinking",
                },
            },
            "required": ["domain", "concept", "probe_type", "score"],
        },
    },
]
