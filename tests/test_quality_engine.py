"""Small deterministic unit tests for the data-quality inspection helpers."""
import unittest
import pandas as pd
from quality_engine import issues_for, issue_details_for, cell_errors_for, metrics, parse_number_word


class QualityEngineTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            "Name": [" Ana ", "Bob", "Bob"],
            "Email": ["ana@example.com", "not-an-email", "not-an-email"],
            "Age": ["20", "twenty", "twenty"],
            "JoinDate": ["2025-01-01", "not-a-date", "not-a-date"],
            "Score": [10, None, None],
        })

    def test_issue_summary_contains_supported_rules(self):
        found = set(issues_for(self.df)["Issue"])
        numeric_candidate = pd.DataFrame({"ScoreText": ["1", "2", "bad", "4", "5"]})
        found |= set(issues_for(numeric_candidate)["Issue"])
        self.assertIn("Missing values", found)
        self.assertIn("Leading/trailing spaces", found)
        self.assertIn("Invalid email format", found)
        self.assertIn("Unparseable dates", found)
        self.assertIn("Possible numeric type mismatch", found)
        self.assertIn("Duplicate rows", found)

    def test_detail_rows_include_row_column_and_recommendation(self):
        details = issue_details_for(self.df)
        self.assertTrue({"Row", "Column", "Original value", "Issue", "Suggested action"}.issubset(details.columns))
        self.assertTrue((details["Issue"] == "Invalid email format").any())
        self.assertTrue((details["Issue"] == "Duplicate row").any())

    def test_duplicate_rows_do_not_unlock_every_cell(self):
        errors = cell_errors_for(self.df)
        # The duplicate row is also independently invalid in several cells, but Name='Bob'
        # is not an error cell solely because the row is duplicated.
        self.assertFalse(bool(errors.loc[1, "Name"]))
        self.assertTrue(bool(errors.loc[1, "Email"]))

    def test_number_words_are_detected_in_numeric_columns(self):
        df = pd.DataFrame({"Age": ["18", "twenty", "thirty-five"]})
        details = issue_details_for(df)
        self.assertTrue((details["Issue"] == "Number written as text").any())
        self.assertEqual(parse_number_word("twenty"), 20)
        self.assertEqual(parse_number_word("thirty-five"), 35)
        self.assertEqual(parse_number_word("one hundred and twenty"), 120)
        self.assertIsNone(parse_number_word("twenty years"))

    def test_metrics_are_bounded(self):
        result = metrics(self.df)
        self.assertEqual(result["Rows"], 3)
        self.assertEqual(result["Columns"], 5)
        self.assertGreaterEqual(result["Indicative quality score"], 0)
        self.assertLessEqual(result["Indicative quality score"], 100)

    def test_inspection_does_not_modify_input(self):
        before = self.df.copy(deep=True)
        issues_for(self.df)
        issue_details_for(self.df)
        cell_errors_for(self.df)
        metrics(self.df)
        pd.testing.assert_frame_equal(self.df, before)


if __name__ == "__main__":
    unittest.main()

    def test_number_word_thirty_five(self):
        self.assertEqual(parse_number_word("thirty-five"), 35)
