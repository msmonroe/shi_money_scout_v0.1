import unittest

from shi.evidence import extract_evidence, verify_review_evidence


class EvidenceTests(unittest.TestCase):
    def test_extracts_compensation_and_buyer_intent(self):
        candidate = {"url": "https://example.com/job", "title": "Remote contract"}
        text = "We are hiring a consultant. Apply now. Pay range $75-$90/hr for a 12 month contract."
        evidence = extract_evidence(candidate, text)
        self.assertTrue(evidence["compensation"])
        self.assertTrue(evidence["buyer_intent"])
        self.assertTrue(evidence["access"])
        self.assertTrue(evidence["duration"])

    def test_rejects_invented_model_quote(self):
        review = {
            "evidence": [
                {"claim": "real", "quote": "Apply now"},
                {"claim": "fake", "quote": "Guaranteed $5000 bonus"},
            ]
        }
        checked = verify_review_evidence(review, "Apply now for this contract role.")
        self.assertEqual(checked["evidence_verified_count"], 1)
        self.assertEqual(checked["evidence_total_count"], 2)
        self.assertEqual(len(checked["evidence_rejected"]), 1)


if __name__ == "__main__":
    unittest.main()
