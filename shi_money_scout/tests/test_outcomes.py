import tempfile
import unittest
from pathlib import Path

from shi.outcomes import opportunity_id, record_outcome, load_outcomes


class OutcomeTests(unittest.TestCase):
    def test_record_and_reload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "outcomes.json"
            url = "https://example.com/role"
            row = record_outcome(path, url, "interview", notes="good call")
            saved = load_outcomes(path)
            self.assertEqual(row["opportunity_id"], opportunity_id(url))
            self.assertEqual(saved[row["opportunity_id"]]["stage"], "interview")
            self.assertEqual(saved[row["opportunity_id"]]["outcome_score"], 0.50)


if __name__ == "__main__":
    unittest.main()
