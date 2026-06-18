import os
import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import create_session_token, get_current_student


class SessionTokenTests(unittest.TestCase):
    def setUp(self):
        os.environ["SESSION_SECRET"] = "test-session-secret-0123456789-abcdef"
        self.student_id = "123e4567-e89b-12d3-a456-426614174000"

    def test_uuid_subject_round_trip(self):
        token, _ = create_session_token(self.student_id, "8015551234")
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        self.assertEqual(get_current_student(credentials), self.student_id)

    def test_tampered_token_is_rejected(self):
        token, _ = create_session_token(self.student_id, "8015551234")
        replacement = "A" if token[-1] != "A" else "B"
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token[:-1] + replacement,
        )
        with self.assertRaises(HTTPException) as raised:
            get_current_student(credentials)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
