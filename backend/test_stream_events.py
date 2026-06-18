import json
import unittest

from backend.agent.stream_events import college_results_event


def valid_payload():
    return {
        "schema_version": "1.0",
        "event": "college_results",
        "recommendation_set_id": "rec_test",
        "generated_at": "2026-06-18T18:30:00Z",
        "query": {
            "text": "Nursing in Utah",
            "requested_program": "Nursing",
            "student_budget_usd": 15000,
            "comparison_requested": True,
        },
        "colleges": [],
    }


class CollegeResultsStreamEventTests(unittest.TestCase):
    def test_accepts_normalized_search_results(self):
        payload = valid_payload()
        self.assertEqual(
            college_results_event("search_colleges", json.dumps(payload)),
            payload,
        )

    def test_ignores_other_tools(self):
        self.assertIsNone(
            college_results_event("update_profile", json.dumps(valid_payload()))
        )

    def test_ignores_tool_errors_and_malformed_output(self):
        self.assertIsNone(
            college_results_event(
                "search_colleges",
                json.dumps({"error": "Database query failed"}),
            )
        )
        self.assertIsNone(college_results_event("search_colleges", "not json"))

    def test_requires_current_contract_version_and_shape(self):
        payload = valid_payload()
        payload["schema_version"] = "2.0"
        self.assertIsNone(
            college_results_event("search_colleges", json.dumps(payload))
        )

        payload = valid_payload()
        payload["colleges"] = {}
        self.assertIsNone(
            college_results_event("search_colleges", json.dumps(payload))
        )


if __name__ == "__main__":
    unittest.main()
