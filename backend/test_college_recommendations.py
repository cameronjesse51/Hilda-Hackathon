import unittest
from datetime import datetime, timezone

from backend.agent.college_recommendations import normalize_college_results


NOW = datetime(2026, 6, 18, 18, 30, tzinfo=timezone.utc)


def profile(*, budget=None, gpa=None, major=""):
    return {
        "academic": {"gpa": gpa, "intended_major": major},
        "hard_constraints": {"max_cost": budget},
    }


class CollegeRecommendationNormalizationTests(unittest.TestCase):
    def test_normalizes_aliases_budget_rates_and_source(self):
        payload = normalize_college_results(
            [{
                "unit_id": 230764,
                "school_name": "Example University",
                "school_city": "Orem",
                "school_state": "UT",
                "avg_net_price": "$13,250",
                "acceptance_rate": 65,
                "completion_rate": 0.71,
                "median_earnings": "58,400",
                "programs": ["Registered Nursing", "Biology"],
                "similarity": 0.873,
            }],
            profile=profile(budget=15000, gpa=3.5),
            filters={"programs": ["Nursing"], "location_state": ["UT"]},
            query="Affordable nursing programs in Utah",
            now=NOW,
        )

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(payload["event"], "college_results")
        self.assertEqual(payload["generated_at"], "2026-06-18T18:30:00Z")
        card = payload["colleges"][0]
        self.assertEqual(card["college_id"], "230764")
        self.assertEqual(card["financials"]["net_price"], 13250)
        self.assertEqual(card["financials"]["budget_difference"], 1750)
        self.assertTrue(card["financials"]["within_budget"])
        self.assertEqual(card["admissions"]["admission_rate"], 0.65)
        self.assertEqual(card["program"]["status"], "available")
        self.assertEqual(card["match_score"], 87.3)
        self.assertIn("College Scorecard", card["sources"][0]["name"])
        self.assertIn("financials.net_price", card["sources"][0]["fields"])

    def test_unknown_data_stays_null_or_unknown(self):
        payload = normalize_college_results(
            [{"id": "school-1", "name": "Sparse College"}],
            profile=profile(),
            filters={},
            query="A good college",
            now=NOW,
        )
        card = payload["colleges"][0]
        self.assertIsNone(card["financials"]["net_price"])
        self.assertIsNone(card["financials"]["within_budget"])
        self.assertIsNone(card["admissions"]["admission_rate"])
        self.assertEqual(card["program"]["status"], "unknown")
        self.assertEqual(card["classification"]["label"], "unknown")

    def test_student_gpa_drives_classification_when_comparison_exists(self):
        payload = normalize_college_results(
            [{
                "id": "school-2",
                "name": "Academic College",
                "admission_rate": 0.55,
                "average_gpa": 3.4,
            }],
            profile=profile(gpa=3.8),
            filters={},
            query="Computer science",
            now=NOW,
        )
        classification = payload["colleges"][0]["classification"]
        self.assertEqual(classification["label"], "likely")
        self.assertEqual(classification["basis"], "student_academic_profile")
        self.assertIn("3.8 GPA is above", classification["reason"])

    def test_gpa_range_and_selectivity_produce_deterministic_classifications(self):
        rows = [
            {
                "id": "range-school",
                "name": "Range College",
                "admission_rate": 0.60,
                "gpa_25th": 3.2,
                "gpa_75th": 3.7,
            },
            {
                "id": "selective-school",
                "name": "Selective College",
                "admission_rate": 0.12,
                "average_gpa": 3.7,
            },
        ]
        payload = normalize_college_results(
            rows,
            profile=profile(gpa=3.9),
            filters={},
            query="Strong academics",
            now=NOW,
        )

        range_fit, selective_fit = [
            college["classification"] for college in payload["colleges"]
        ]
        self.assertEqual(range_fit["label"], "likely")
        self.assertIn("3.2-3.7 GPA range", range_fit["reason"])
        self.assertEqual(selective_fit["label"], "reach")
        self.assertIn("12%", selective_fit["reason"])
        self.assertEqual(selective_fit["basis"], "student_academic_profile")

    def test_admission_rate_only_rule_explains_its_limitation(self):
        payload = normalize_college_results(
            [{"id": "open-school", "name": "Open College", "admission_rate": 0.82}],
            profile=profile(),
            filters={},
            query="Accessible colleges",
            now=NOW,
        )
        classification = payload["colleges"][0]["classification"]
        self.assertEqual(classification["label"], "likely")
        self.assertEqual(classification["basis"], "admission_rate_only")
        self.assertIn("GPA data is unavailable", classification["reason"])

    def test_match_reasons_are_ordered_and_evidence_based(self):
        payload = normalize_college_results(
            [{
                "id": "reason-school",
                "name": "Reason College",
                "state": "UT",
                "net_price": 14000,
                "admission_rate": 0.60,
                "graduation_rate": 0.74,
                "median_earnings_10yr": 61000,
                "programs": ["Nursing"],
            }],
            profile=profile(budget=15000, gpa=3.5),
            filters={"programs": ["Nursing"], "location_state": ["UT"]},
            query="Affordable nursing in Utah",
            now=NOW,
        )
        reasons = payload["colleges"][0]["match_reasons"]
        self.assertEqual(
            [reason["category"] for reason in reasons],
            ["program", "financial", "academic", "location", "outcomes"],
        )
        self.assertTrue(all(reason["evidence"] for reason in reasons))
        self.assertIn("$14,000 net price", reasons[1]["evidence"])

    def test_card_classification_and_reasons_are_repeatable(self):
        row = {
            "id": "repeatable-school",
            "name": "Repeatable College",
            "net_price": 11000,
            "admission_rate": 0.48,
            "average_gpa": 3.5,
            "graduation_rate": 0.68,
        }
        arguments = {
            "profile": profile(budget=13000, gpa=3.6),
            "filters": {},
            "query": "Affordable target schools",
            "now": NOW,
        }
        first = normalize_college_results([row], **arguments)["colleges"][0]
        second = normalize_college_results([row], **arguments)["colleges"][0]
        self.assertEqual(first["classification"], second["classification"])
        self.assertEqual(first["match_reasons"], second["match_reasons"])

    def test_source_links_preserve_provenance_and_avoid_fake_record_ids(self):
        payload = normalize_college_results(
            [{
                "name": "Source College",
                "source_name": "IPEDS",
                "source_url": "https://nces.ed.gov/ipeds/datacenter/",
                "source_retrieved_at": "2026-06-17T12:00:00Z",
                "net_price": 9000,
            }],
            profile=profile(),
            filters={},
            query="Source-backed schools",
            now=NOW,
        )
        source = payload["colleges"][0]["sources"][0]
        self.assertEqual(source["name"], "IPEDS")
        self.assertEqual(source["url"], "https://nces.ed.gov/ipeds/datacenter/")
        self.assertEqual(source["retrieved_at"], "2026-06-17T12:00:00Z")

        synthetic = normalize_college_results(
            [{"name": "No Identifier College"}],
            profile=profile(),
            filters={},
            query="Unknown ID",
            now=NOW,
        )["colleges"][0]
        self.assertEqual(
            synthetic["sources"][0]["url"],
            "https://collegescorecard.ed.gov/",
        )

    def test_filter_budget_is_used_when_profile_budget_is_missing(self):
        payload = normalize_college_results(
            [{"id": "school-3", "name": "Budget College", "net_price": 12000}],
            profile=profile(),
            filters={"max_net_price": 10000},
            query="Affordable colleges",
            now=NOW,
        )
        financials = payload["colleges"][0]["financials"]
        self.assertEqual(financials["student_budget"], 10000)
        self.assertEqual(financials["budget_difference"], -2000)
        self.assertFalse(financials["within_budget"])


if __name__ == "__main__":
    unittest.main()
