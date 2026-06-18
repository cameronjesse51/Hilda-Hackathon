import os
import unittest
from unittest.mock import patch

from backend.sms_config import welcome_sms_enabled


class SmsConfigurationTests(unittest.TestCase):
    def test_welcome_sms_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ENABLE_WELCOME_SMS", None)
            self.assertFalse(welcome_sms_enabled())

    def test_welcome_sms_requires_explicit_opt_in(self):
        for value in ("true", "1", "yes", "on"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"ENABLE_WELCOME_SMS": value}):
                    self.assertTrue(welcome_sms_enabled())

        with patch.dict(os.environ, {"ENABLE_WELCOME_SMS": "false"}):
            self.assertFalse(welcome_sms_enabled())


if __name__ == "__main__":
    unittest.main()
