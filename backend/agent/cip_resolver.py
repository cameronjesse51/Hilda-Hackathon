"""Resolve free-text program names to CIP codes via the study_areas_by_code catalog."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

CREDENTIAL_LEVELS = {
    "certificate": "Certificate",
    "associate": "Associate's degree",
    "bachelor": "Bachelor's degree",
    "master": "Master's degree",
    "doctoral": "Doctor's degree",
}

_cip_cache: dict[str, list[str]] = {}


def resolve_cip_codes(db, program_text: str) -> list[str]:
    """Look up CIP codes for a program name using the study_areas_by_code catalog.

    Returns a list of CIP code strings, or an empty list if resolution fails
    (which lets the existing ILIKE fallback in the RPC take over).
    """
    if not program_text:
        return []

    cache_key = program_text.strip().lower()
    if cache_key in _cip_cache:
        return _cip_cache[cache_key]

    try:
        catalog_rows = (
            db.table("study_areas_by_code")
            .select("cipdesc")
            .ilike("cipdesc", f"%{program_text}%")
            .execute()
            .data or []
        )
        if not catalog_rows:
            _cip_cache[cache_key] = []
            return []

        matched_descriptions = [
            row["cipdesc"] for row in catalog_rows if row.get("cipdesc")
        ]
        if not matched_descriptions:
            _cip_cache[cache_key] = []
            return []

        specialty_rows = (
            db.table("institution_specialties")
            .select('"CIPCODE"')
            .in_('"CIPDESC"', matched_descriptions)
            .execute()
            .data or []
        )
        codes = sorted({
            str(row["CIPCODE"])
            for row in specialty_rows
            if row.get("CIPCODE") is not None
        })
        _cip_cache[cache_key] = codes
        return codes

    except Exception as exc:
        log.warning("CIP code resolution failed for %r: %s", program_text, exc)
        return []
