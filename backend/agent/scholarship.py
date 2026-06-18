"""Scholarship search handler for the Halda agent.

Uses the Brave Search API to find live scholarship opportunities tailored
to the student's profile and returns structured results with source URLs.
Falls back gracefully if the API key is not configured.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Domains we trust for scholarship info — used to lightly boost ranking
TRUSTED_SCHOLARSHIP_DOMAINS = frozenset({
    "fastweb.com",
    "scholarships.com",
    "bold.org",
    "collegeboard.org",
    "studentaid.gov",
    "niche.com",
    "unigo.com",
    "cappex.com",
    "chegg.com",
    "petersons.com",
    "careeronestop.org",
})

# Terms that signal a result is actually a scholarship listing (vs. a general article)
SCHOLARSHIP_SIGNAL_TERMS = (
    "scholarship", "grant", "award", "fellowship", "stipend", "bursary",
    "financial aid", "apply now", "deadline", "eligibility",
)


def _domain(url: str) -> str:
    """Extract cleaned domain from a URL."""
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except Exception:
        return url


def _build_query(tool_input: dict, profile: dict) -> str:
    """Enrich the agent's query with profile signals the student has already shared."""
    base = tool_input.get("query", "scholarships for college students")
    filters = tool_input.get("filters", {})

    parts = [base]

    # Append major if not already in query and known from profile
    if not filters.get("major"):
        major = profile.get("academic", {}).get("intended_major")
        if major and major.lower() not in base.lower():
            parts.append(f"{major} major")

    # Append state if not already in query
    if not filters.get("state"):
        locs = profile.get("stated", {}).get("location_pref") or []
        if isinstance(locs, str):
            locs = [locs]
        if locs and locs[0].lower() not in base.lower():
            parts.append(f"in {locs[0]}")

    # International student flag
    if profile.get("hard_constraints", {}).get("visa_required"):
        parts.append("international students F-1 visa")

    # Need-based / merit signals
    if filters.get("need_based"):
        parts.append("need-based")
    if filters.get("merit_based"):
        parts.append("merit scholarship")

    # Keep results fresh by including current year
    year = datetime.now().year
    if str(year) not in base:
        parts.append(str(year))

    return " ".join(parts)


def _search_brave(query: str, result_count: int) -> list[dict]:
    """Call Brave Search API and return raw result dicts."""
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        log.warning("BRAVE_SEARCH_API_KEY not configured — skipping live search")
        return []

    try:
        response = httpx.get(
            BRAVE_ENDPOINT,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": min(result_count * 4, 20),  # over-fetch then filter
                "safesearch": "strict",
                "freshness": "py",  # past year — keep results current
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("web", {}).get("results", [])
    except httpx.HTTPStatusError as exc:
        log.error("Brave Search HTTP error %s: %s", exc.response.status_code, exc)
        return []
    except Exception as exc:
        log.error("Brave Search failed: %s", exc)
        return []


def _score_result(item: dict) -> int:
    """Assign a relevance score to a raw search result (higher = better)."""
    text = f"{item.get('title', '')} {item.get('description', '')}".lower()
    domain = _domain(item.get("url", ""))
    score = 0

    # Reward trusted scholarship aggregator domains
    if domain in TRUSTED_SCHOLARSHIP_DOMAINS:
        score += 10

    # Reward results that use scholarship-specific language
    for term in SCHOLARSHIP_SIGNAL_TERMS:
        if term in text:
            score += 2

    # Penalise results that look like news articles or ad pages
    if any(kw in text for kw in ("sponsored", "advertisement", "cookie policy")):
        score -= 5

    return score


def _format_results(raw: list[dict], limit: int) -> list[dict]:
    """Filter, score, deduplicate, and normalize Brave results."""
    # Sort by our relevance heuristic
    ranked = sorted(raw, key=_score_result, reverse=True)

    seen_urls: set[str] = set()
    results: list[dict] = []

    for item in ranked:
        url = item.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip results with no scholarship signal at all
        text = f"{item.get('title', '')} {item.get('description', '')}".lower()
        if not any(term in text for term in SCHOLARSHIP_SIGNAL_TERMS):
            continue

        results.append({
            "title": item.get("title", "Scholarship Opportunity").strip(),
            "url": url,
            "description": (item.get("description") or "").strip(),
            "source": item.get("profile", {}).get("name") or _domain(url),
            "is_trusted_source": _domain(url) in TRUSTED_SCHOLARSHIP_DOMAINS,
        })

        if len(results) >= limit:
            break

    return results


def _fallback_resources() -> list[dict]:
    """Return well-known scholarship aggregator sites when live search is unavailable."""
    return [
        {
            "title": "Fastweb — Free Scholarship Search",
            "url": "https://www.fastweb.com",
            "description": "Largest free scholarship search engine. Match your profile to thousands of scholarships.",
            "source": "fastweb.com",
            "is_trusted_source": True,
        },
        {
            "title": "Bold.org — Apply to Exclusive Scholarships",
            "url": "https://bold.org/scholarships/",
            "description": "Curated scholarships with fast applications, including many for specific majors and demographics.",
            "source": "bold.org",
            "is_trusted_source": True,
        },
        {
            "title": "College Board Scholarship Search",
            "url": "https://bigfuture.collegeboard.org/scholarship-search",
            "description": "Official College Board scholarship finder — over 2,000 programs worth $6 billion.",
            "source": "collegeboard.org",
            "is_trusted_source": True,
        },
        {
            "title": "Federal Student Aid — Grants & Scholarships",
            "url": "https://studentaid.gov/understand-aid/types/scholarships",
            "description": "Official U.S. government resource for federal grants and links to state scholarship programs.",
            "source": "studentaid.gov",
            "is_trusted_source": True,
        },
        {
            "title": "Scholarships.com — Free Search & Matching",
            "url": "https://www.scholarships.com",
            "description": "Browse by major, state, GPA, and more. Over 3.7 million scholarships listed.",
            "source": "scholarships.com",
            "is_trusted_source": True,
        },
    ]


def handle_search_scholarships(tool_input: dict, profile: dict) -> tuple[str, dict]:
    """Main handler for the search_scholarships tool.

    Builds a profile-enriched query, calls Brave Search, filters and ranks
    results, and returns a JSON payload suitable for SSE emission.
    """
    limit = max(1, min(int(tool_input.get("limit", 5)), 10))
    query = _build_query(tool_input, profile)
    filters = tool_input.get("filters", {})

    log.info("search_scholarships: query=%r filters=%s", query, json.dumps(filters))

    raw_results = _search_brave(query, limit)
    scholarships = _format_results(raw_results, limit)

    used_fallback = False
    if not scholarships:
        log.info("search_scholarships: no live results — using fallback resources")
        scholarships = _fallback_resources()[:limit]
        used_fallback = True

    payload = {
        "event": "scholarship_results",
        "query": query,
        "scholarships": scholarships,
        "total_found": len(scholarships),
        "used_fallback": used_fallback,
        "filters_applied": {k: v for k, v in filters.items() if v is not None},
    }

    return json.dumps(payload), profile
