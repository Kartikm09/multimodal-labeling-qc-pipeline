import unittest

from qc_pipeline.qc import evaluate_rows


class QcTests(unittest.TestCase):
    def test_evaluate_rows_detects_low_confidence_and_missing_notes(self):
        rows = [
            {"asset_id": "a1", "modality": "video", "label": "", "confidence": "0.4", "reviewer_notes": ""},
        ]

        issues = evaluate_rows(rows)

        self.assertEqual(issues[0]["issues"], ["low-confidence", "missing-label", "missing-reviewer-notes"])


if __name__ == "__main__":
    unittest.main()
