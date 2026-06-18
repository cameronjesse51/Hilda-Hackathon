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
    def test_marks_explicit_comparison_request_for_the_client(self):
        payload = normalize_college_results(
            [{"id": "one", "name": "One"}, {"id": "two", "name": "Two"}],
            profile=profile(),
            filters={},
            query="Compare these schools",
            comparison_requested=True,
            now=NOW,
        )

        self.assertTrue(payload["query"]["comparison_requested"])

    def test_normalizes_aliases_budget_rates_and_source(self):
        payload = normalize_college_results(
            [{
                "unit_id": 230764,
                "school_name": "Example University",
                "school_city": "Orem",
                "school_state": "UT",
                "control": 1,
                "net_price_pub": "$13,250",
                "net_price_priv": "$99,999",
                "acceptance_rate": 65,
                "sat_avg": 1210,
                "completion_rate": 0.71,
                "transfer_rate": 0.08,
                "median_earnings_10y": "58,400",
                "median_grad_debt": "18,500",
                "enrollment": 12400,
                "pct_pell": 0.31,
                "pct_international": 0.06,
                "net_price_year": "2023-24",
                "debt_year": 2023,
                "admissions_year": 2024,
                "completion_year": 2023,
                "earnings_year": 2021,
                "campus_year": 2024,
                "program_year": "2023-24",
                "programs": ["Registered Nursing", "Biology"],
                "program_cip_codes": ["51.3801"],
                "program_awards_last_year": 42,
                "similarity": 0.873,
            }],
            profile=profile(budget=15000, gpa=3.5),
            filters={"programs": ["Nursing"], "location_state": ["UT"]},
            query="Affordable nursing programs in Utah",
            now=NOW,
        )

        self.assertEqual(payload["schema_version"], "2.0")
        self.assertEqual(payload["event"], "college_results")
        self.assertEqual(payload["generated_at"], "2026-06-18T18:30:00Z")
        card = payload["colleges"][0]
        self.assertEqual(
            set(card),
            {
                "college_id", "name", "location", "cost", "admissions",
                "outcomes", "campus", "program_fit", "fit", "sources",
            },
        )
        self.assertNotIn("financials", card)
        self.assertNotIn("match_score", card)
        self.assertEqual(card["college_id"], "230764")
        self.assertEqual(card["cost"]["facts"]["net_price"], 13250)
        self.assertEqual(card["cost"]["personalized"]["budget_difference"], 1750)
        self.assertTrue(card["cost"]["personalized"]["within_budget"])
        self.assertEqual(card["cost"]["facts"]["source_years"]["net_price"], "2023-24")
        self.assertEqual(card["cost"]["facts"]["source_years"]["median_grad_debt"], 2023)
        self.assertEqual(card["admissions"]["facts"]["admission_rate"], 0.65)
        self.assertEqual(card["admissions"]["facts"]["sat_average"], 1210)
        self.assertEqual(card["cost"]["facts"]["median_grad_debt"], 18500)
        self.assertEqual(card["outcomes"]["facts"]["transfer_rate"], 0.08)
        self.assertEqual(card["outcomes"]["facts"]["median_earnings_10yr"], 58400)
        self.assertEqual(card["outcomes"]["facts"]["source_years"]["earnings"], 2021)
        self.assertEqual(card["campus"]["facts"]["enrollment"], 12400)
        self.assertEqual(card["campus"]["facts"]["control"], "public")
        self.assertEqual(card["campus"]["facts"]["pell_recipient_rate"], 0.31)
        self.assertEqual(card["campus"]["facts"]["international_rate"], 0.06)
        self.assertEqual(card["program_fit"]["personalized"]["status"], "available")
        self.assertEqual(card["program_fit"]["facts"]["matched_programs"], ["Registered Nursing", "Biology"])
        self.assertEqual(card["program_fit"]["facts"]["cip_codes"], ["51.3801"])
        self.assertEqual(card["program_fit"]["facts"]["awards_last_year"], 42)
        self.assertEqual(card["fit"]["score"], 87.3)
        self.assertIn("College Scorecard", card["sources"][0]["name"])
        self.assertIn("cost.facts.net_price", card["sources"][0]["fields"])

    def test_unknown_data_stays_null_or_unknown(self):
        payload = normalize_college_results(
            [{"id": "school-1", "name": "Sparse College"}],
            profile=profile(),
            filters={},
            query="A good college",
            now=NOW,
        )
        card = payload["colleges"][0]
        self.assertIsNone(card["cost"]["facts"]["net_price"])
        self.assertIsNone(card["cost"]["personalized"]["within_budget"])
        self.assertIsNone(card["admissions"]["facts"]["admission_rate"])
        self.assertEqual(card["program_fit"]["personalized"]["status"], "unknown")
        self.assertEqual(card["admissions"]["personalized"]["classification"]["label"], "unknown")
        self.assertIsNone(card["cost"]["facts"]["median_grad_debt"])
        self.assertIsNone(card["admissions"]["facts"]["sat_average"])
        self.assertIsNone(card["outcomes"]["facts"]["transfer_rate"])
        self.assertEqual(
            card["campus"]["facts"],
            {
                "enrollment": None,
                "control": None,
                "size_category": None,
                "pell_recipient_rate": None,
                "international_rate": None,
                "source_year": None,
            },
        )

    def test_private_control_selects_private_net_price(self):
        payload = normalize_college_results(
            [{
                "unitid": "private-school",
                "name": "Private College",
                "control": 2,
                "net_price_pub": 9000,
                "net_price_priv": 24000,
            }],
            profile=profile(),
            filters={},
            query="Private colleges",
            now=NOW,
        )

        card = payload["colleges"][0]
        self.assertEqual(card["cost"]["facts"]["net_price"], 24000)
        self.assertEqual(card["campus"]["facts"]["control"], "private_nonprofit")

    def test_aggregated_rpc_program_fields_map_to_program_status(self):
        payload = normalize_college_results(
            [{
                "unitid": "program-school",
                "name": "Program College",
                "programs": ["Computer and Information Sciences, General"],
                "program_cip_codes": ["11"],
                "program_awards_last_year": 42,
            }],
            profile=profile(major="Computer and Information Sciences"),
            filters={},
            query="Computer science programs",
            now=NOW,
        )

        program = payload["colleges"][0]["program_fit"]
        self.assertEqual(program["personalized"]["status"], "available")
        self.assertEqual(program["facts"]["cip_codes"], ["11"])

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
        classification = payload["colleges"][0]["admissions"]["personalized"]["classification"]
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
            college["admissions"]["personalized"]["classification"] for college in payload["colleges"]
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
        classification = payload["colleges"][0]["admissions"]["personalized"]["classification"]
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
        reasons = payload["colleges"][0]["fit"]["reasons"]
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
        self.assertEqual(first["admissions"]["personalized"], second["admissions"]["personalized"])
        self.assertEqual(first["fit"]["reasons"], second["fit"]["reasons"])

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
        cost_fit = payload["colleges"][0]["cost"]["personalized"]
        self.assertEqual(cost_fit["student_budget"], 10000)
        self.assertEqual(cost_fit["budget_difference"], -2000)
        self.assertFalse(cost_fit["within_budget"])


if __name__ == "__main__":
    unittest.main()
