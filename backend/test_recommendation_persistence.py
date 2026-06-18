import unittest

from backend.agent.tool_handlers import _recommendation_record


class RecommendationPersistenceTests(unittest.TestCase):
    def test_record_is_tenant_scoped_and_excludes_contact_and_history(self):
        payload = {
            "recommendation_set_id": "rec_123",
            "schema_version": "2.0",
            "generated_at": "2026-06-18T18:30:00Z",
            "query": {"text": "Nursing", "requested_program": "Nursing"},
            "colleges": [{"college_id": "230764", "name": "Example"}],
        }
        profile = {
            "student_id": "123e4567-e89b-12d3-a456-426614174000",
            "contact": {"phone": "+18015551234", "email": "student@example.com"},
            "academic": {"gpa": 3.8},
            "stated": {"interests": ["healthcare"]},
            "hard_constraints": {"max_cost": 15000},
            "confidence_scores": {"career_clarity": 0.8},
            "stage": "senior",
            "session_history": [{"role": "user", "content": "private"}],
        }

        record = _recommendation_record(payload, profile)

        self.assertEqual(record["id"], "rec_123")
        self.assertEqual(record["student_id"], profile["student_id"])
        self.assertEqual(record["recommendations"], payload["colleges"])
        self.assertNotIn("contact", record["profile_snapshot"])
        self.assertNotIn("session_history", record["profile_snapshot"])


if __name__ == "__main__":
    unittest.main()
