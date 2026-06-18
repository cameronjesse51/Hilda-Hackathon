import base64
import binascii
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


bearer = HTTPBearer(auto_error=False)


def _decode_segment(segment: str) -> dict:
    padding = "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(segment + padding))


def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authentication required")

    secret = os.environ.get("SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must be set to at least 32 characters")

    try:
        header_segment, payload_segment, signature_segment = credentials.credentials.split(".")
        header = _decode_segment(header_segment)
        payload = _decode_segment(payload_segment)
        unsigned_token = f"{header_segment}.{payload_segment}".encode()
        expected_signature = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), unsigned_token, hashlib.sha256).digest()
        ).rstrip(b"=").decode()

        if header.get("alg") != "HS256" or not hmac.compare_digest(
            signature_segment, expected_signature
        ):
            raise ValueError("Invalid signature")
        if payload.get("iss") != "halda" or int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("Expired token")
        student_id = payload.get("sub")
        if not isinstance(student_id, str) or not student_id:
            raise ValueError("Missing subject")
        return student_id
    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError,
        binascii.Error,
        UnicodeDecodeError,
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired session")
