import unittest

from backend.agent.profile import empty_profile
from backend.agent.system_prompt import build_system_prompt
from backend.agent.tools import TOOLS


class SystemPromptTests(unittest.TestCase):
    def setUp(self):
        self.profile = empty_profile("123e4567-e89b-12d3-a456-426614174000")

    def test_sophomore_explicit_college_request_overrides_deferral(self):
        prompt = build_system_prompt(self.profile)

        self.assertIn(
            "explicit request in their latest message takes priority",
            prompt,
        )
        self.assertIn(
            "An explicit request always authorizes an immediate search",
            prompt,
        )
        self.assertIn("comparison_requested to true", prompt)
        self.assertNotIn("End every session with a hook", prompt)
        self.assertNotIn("before we talk again", prompt)

    def test_search_tool_allows_explicit_requests_at_low_confidence(self):
        search_tool = next(tool for tool in TOOLS if tool["name"] == "search_colleges")

        self.assertIn("Call this immediately", search_tool["description"])
        self.assertIn("regardless of confidence scores", search_tool["description"])


if __name__ == "__main__":
    unittest.main()
