import os
import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import create_session_token, get_current_student, validate_dev_auth_key


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


class DeveloperAuthTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ENABLE_DEV_AUTH", None)
        os.environ.pop("DEV_AUTH_KEY", None)
        os.environ.pop("DEV_AUTH_PHONE", None)

    def tearDown(self):
        os.environ.pop("ENABLE_DEV_AUTH", None)
        os.environ.pop("DEV_AUTH_KEY", None)
        os.environ.pop("DEV_AUTH_PHONE", None)

    def test_bypass_is_hidden_when_disabled(self):
        with self.assertRaises(HTTPException) as raised:
            validate_dev_auth_key("anything")
        self.assertEqual(raised.exception.status_code, 404)

    def test_valid_key_returns_dedicated_normalized_phone(self):
        os.environ["ENABLE_DEV_AUTH"] = "true"
        os.environ["DEV_AUTH_KEY"] = "developer-key-0123456789abcdef"
        os.environ["DEV_AUTH_PHONE"] = "801-555-1234"
        self.assertEqual(
            validate_dev_auth_key("developer-key-0123456789abcdef"),
            "+18015551234",
        )

    def test_invalid_key_is_rejected(self):
        os.environ["ENABLE_DEV_AUTH"] = "true"
        os.environ["DEV_AUTH_KEY"] = "developer-key-0123456789abcdef"
        os.environ["DEV_AUTH_PHONE"] = "+18015551234"
        with self.assertRaises(HTTPException) as raised:
            validate_dev_auth_key("wrong")
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
