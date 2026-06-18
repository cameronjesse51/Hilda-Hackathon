import unittest

from backend.agent.tool_handlers import (
    _canonicalize_college_row,
    _college_rpc_params,
    _combine_college_results,
    _location_states,
    _structured_fallback_rows,
)


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeCollegeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def select(self, fields):
        self.calls.append(("select", fields))
        return self

    def is_(self, field, value):
        self.calls.append(("is", field, value))
        return self

    def gte(self, field, value):
        self.calls.append(("gte", field, value))
        return self

    def in_(self, field, values):
        self.calls.append(("in", field, values))
        return self

    def order(self, field, **kwargs):
        self.calls.append(("order", field, kwargs))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def execute(self):
        return FakeResponse(self.rows)


class FakeDb:
    def __init__(self, rows):
        self.query = FakeCollegeQuery(rows)

    def table(self, name):
        if name != "college_embeddings":
            raise AssertionError(f"Unexpected table: {name}")
        return self.query


class CollegeSearchFallbackTests(unittest.TestCase):
    def test_rpc_receives_size_and_requested_program_filters(self):
        params = _college_rpc_params(
            [0.1, 0.2],
            {
                "school_size": "medium",
                "programs": ["Computer Science"],
                "location_state": ["CO"],
            },
            {},
            5,
        )

        self.assertEqual(params["filter_school_size"], "medium")
        self.assertEqual(params["requested_program"], "Computer Science")
        self.assertEqual(params["filter_state"], ["CO"])
        self.assertTrue(params["requires_cs"])

    def test_rpc_uses_profile_major_when_program_filter_is_absent(self):
        params = _college_rpc_params(
            [0.1],
            {},
            {"academic": {"intended_major": "Biology"}},
            3,
        )

        self.assertEqual(params["requested_program"], "Biology")

    def test_recovers_colorado_from_natural_language(self):
        self.assertEqual(
            _location_states("I am looking for a school in Colorado", {}),
            ["CO"],
        )
        self.assertEqual(_location_states("Schools near Denver, CO", {}), ["CO"])

    def test_explicit_location_filter_wins_over_query_text(self):
        self.assertEqual(
            _location_states(
                "Maybe Colorado",
                {"location_state": ["Utah"]},
            ),
            ["UT"],
        )

    def test_state_names_from_profile_preferences_can_be_recovered(self):
        preferences = ["Colorado", "New Mexico"]
        self.assertEqual(_location_states(" ".join(preferences), {}), ["CO", "NM"])

    def test_structured_fallback_uses_unembedded_degree_schools(self):
        db = FakeDb([
            {
                "unitid": "co-university",
                "name": "Colorado University",
                "state": "CO",
                "pred_degree": 3,
                "control": 1,
                "net_price_pub": 14000,
                "graduation_rate": 0.72,
            },
            {
                "unitid": "co-beauty",
                "name": "Colorado Beauty School",
                "state": "CO",
                "pred_degree": 1,
                "control": 2,
                "net_price_priv": 9000,
                "graduation_rate": 0.95,
            },
            {
                "unitid": "ut-university",
                "name": "Utah University",
                "state": "UT",
                "pred_degree": 3,
                "control": 1,
                "net_price_pub": 10000,
                "graduation_rate": 0.80,
            },
        ])

        rows = _structured_fallback_rows(
            db,
            {"location_state": ["CO"]},
            "A good university in Colorado",
            5,
        )

        self.assertEqual([row["unitid"] for row in rows], ["co-university"])
        self.assertEqual(rows[0]["net_price"], 14000)
        self.assertIn(("is", "embedding", "null"), db.query.calls)
        self.assertIn(("gte", "pred_degree", 2), db.query.calls)
        self.assertIn(("in", "state", ["CO"]), db.query.calls)

    def test_vocational_query_allows_certificate_school(self):
        db = FakeDb([{
            "unitid": "co-beauty",
            "name": "Colorado Beauty School",
            "state": "CO",
            "pred_degree": 1,
            "control": 2,
            "net_price_priv": 9000,
        }])

        rows = _structured_fallback_rows(
            db,
            {"location_state": ["CO"]},
            "Cosmetology certificate in Colorado",
            5,
        )

        self.assertEqual([row["unitid"] for row in rows], ["co-beauty"])
        self.assertIn(("gte", "pred_degree", 1), db.query.calls)

    def test_hard_location_constraint_removes_semantic_results(self):
        results = _combine_college_results(
            [{"unitid": "ut", "name": "Utah Match", "state": "UT"}],
            [{"unitid": "co", "name": "Colorado Fallback", "state": "CO", "pred_degree": 3}],
            {"location_state": ["CO"]},
            "Schools in Colorado",
            5,
        )

        self.assertEqual([row["unitid"] for row in results], ["co"])

    def test_structured_aliases_are_available_to_existing_card_contract(self):
        row = _canonicalize_college_row({
            "control": 2,
            "net_price_priv": 18000,
            "median_earnings_10y": 62000,
            "pct_nursing": 0.12,
        })

        self.assertEqual(row["net_price"], 18000)
        self.assertEqual(row["median_earnings_10yr"], 62000)
        self.assertTrue(row["has_nursing"])


if __name__ == "__main__":
    unittest.main()
