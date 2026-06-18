"""Resolve free-text program names to CIP codes via the study_areas_by_code catalog."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

log = logging.getLogger(__name__)

CREDENTIAL_LEVELS = {
    "certificate": "Certificate",
    "associate": "Associate's degree",
    "bachelor": "Bachelor's degree",
    "master": "Master's degree",
    "doctoral": "Doctor's degree",
}

_cip_cache: dict[str, list[str]] = {}
_all_cip_descs: list[str] | None = None  # lazy-loaded full CIP catalog


def _load_all_cip_descs(db) -> list[str]:
    global _all_cip_descs
    if _all_cip_descs is not None:
        return _all_cip_descs
    try:
        rows = (
            db.table("study_areas_by_code")
            .select("cipdesc")
            .execute()
            .data or []
        )
        _all_cip_descs = [r["cipdesc"] for r in rows if r.get("cipdesc")]
        log.info("Loaded %d CIP descriptions for fuzzy fallback", len(_all_cip_descs))
    except Exception as exc:
        log.warning("Could not load CIP catalog for fuzzy fallback: %s", exc)
        _all_cip_descs = []
    return _all_cip_descs


def _fuzzy_match_cip_desc(descriptions: list[str], query: str, threshold: float = 0.4) -> str | None:
    """Return the CIP_DESC with the highest character-sequence similarity to query, or None."""
    q = query.lower()
    best_desc, best_score = None, 0.0
    for desc in descriptions:
        score = SequenceMatcher(None, q, desc.lower()).ratio()
        if score > best_score:
            best_score = score
            best_desc = desc
    if best_score >= threshold:
        return best_desc
    return None


def resolve_cip_codes(db, program_text: str) -> list[str]:
    """Look up CIP codes for a program name using the study_areas_by_code catalog.

    study_areas_by_code schema:
        cipcode     bigint  NOT NULL
        cipdesc     text
        uuid        uuid    NOT NULL
        exists_in_institution  boolean

    First tries an exact substring match (ILIKE) against the catalog.  If that
    returns nothing — because the AI phrased the program differently from the
    canonical CIP label — falls back to fuzzy character-sequence matching against
    the full catalog so that e.g. "pipe fitting" → "Pipefitting/Pipefitter".

    Returns a list of CIP code strings, or an empty list if resolution fails
    (which lets the existing ILIKE fallback in the RPC take over).
    """
    if not program_text:
        return []

    cache_key = program_text.strip().lower()
    if cache_key in _cip_cache:
        return _cip_cache[cache_key]

    try:
        # 1. Fast path: substring match against the catalog
        catalog_rows = (
            db.table("study_areas_by_code")
            .select("cipcode")
            .ilike("cipdesc", f"%{program_text}%")
            .eq("exists_in_institution", True)
            .execute()
            .data or []
        )

        # 2. Fuzzy fallback: load full catalog and find the closest description,
        #    then re-query by exact description to get its cipcode
        if not catalog_rows:
            all_descs = _load_all_cip_descs(db)
            best = _fuzzy_match_cip_desc(all_descs, program_text)
            if best:
                log.info("CIP fuzzy match: %r → %r", program_text, best)
                catalog_rows = (
                    db.table("study_areas_by_code")
                    .select("cipcode")
                    .eq("cipdesc", best)
                    .eq("exists_in_institution", True)
                    .execute()
                    .data or []
                )

        if not catalog_rows:
            _cip_cache[cache_key] = []
            return []

        codes = sorted({
            str(row["cipcode"])
            for row in catalog_rows
            if row.get("cipcode") is not None
        })
        _cip_cache[cache_key] = codes
        return codes

    except Exception as exc:
        log.warning("CIP code resolution failed for %r: %s", program_text, exc)
        return []
