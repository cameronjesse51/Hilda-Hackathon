import unittest
from unittest.mock import MagicMock

from backend.agent.cip_resolver import resolve_cip_codes, CREDENTIAL_LEVELS, _cip_cache


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, data):
        self._data = data

    def select(self, fields):
        return self

    def ilike(self, field, pattern):
        return self

    def in_(self, field, values):
        return self

    def execute(self):
        return FakeResponse(self._data)


class CipResolverTests(unittest.TestCase):
    def setUp(self):
        _cip_cache.clear()

    def _make_db(self, catalog_data, specialty_data):
        db = MagicMock()
        catalog_query = FakeQuery(catalog_data)
        specialty_query = FakeQuery(specialty_data)
        def table_router(name):
            if name == "study_areas_by_code":
                return catalog_query
            if name == "institution_specialties":
                return specialty_query
            raise AssertionError(f"Unexpected table: {name}")
        db.table = table_router
        return db

    def test_resolves_program_to_cip_codes(self):
        db = self._make_db(
            catalog_data=[{"CIP_DESC": "Computer and Information Sciences"}],
            specialty_data=[
                {"CIPCODE": "11.0101"},
                {"CIPCODE": "11.0701"},
                {"CIPCODE": "11.0101"},
            ],
        )
        codes = resolve_cip_codes(db, "Computer Science")
        self.assertEqual(codes, ["11.0101", "11.0701"])

    def test_returns_empty_for_unknown_program(self):
        db = self._make_db(catalog_data=[], specialty_data=[])
        codes = resolve_cip_codes(db, "Underwater Basket Weaving")
        self.assertEqual(codes, [])

    def test_returns_empty_for_blank_input(self):
        db = MagicMock()
        self.assertEqual(resolve_cip_codes(db, ""), [])
        db.table.assert_not_called()

    def test_caches_results(self):
        db = self._make_db(
            catalog_data=[{"CIP_DESC": "Nursing"}],
            specialty_data=[{"CIPCODE": "51.3801"}],
        )
        first = resolve_cip_codes(db, "Nursing")
        second = resolve_cip_codes(db, "nursing")
        self.assertEqual(first, second)

    def test_graceful_failure_on_db_error(self):
        db = MagicMock()
        db.table.side_effect = Exception("connection refused")
        codes = resolve_cip_codes(db, "Nursing")
        self.assertEqual(codes, [])

    def test_credential_levels_mapping(self):
        self.assertEqual(CREDENTIAL_LEVELS["bachelor"], "Bachelor's degree")
        self.assertEqual(CREDENTIAL_LEVELS["master"], "Master's degree")
        self.assertIn("certificate", CREDENTIAL_LEVELS)
        self.assertIn("doctoral", CREDENTIAL_LEVELS)


if __name__ == "__main__":
    unittest.main()
