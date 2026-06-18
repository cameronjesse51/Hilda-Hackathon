import re


def normalize_phone_e164(phone: str) -> str:
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)

    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if raw.startswith("+") and 8 <= len(digits) <= 15 and not digits.startswith("0"):
        return f"+{digits}"
    raise ValueError("Phone number must be a valid E.164 or 10-digit US number")
