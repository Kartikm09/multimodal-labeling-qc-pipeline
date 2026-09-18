import json
import unittest
from pathlib import Path
from fractions import Fraction

from qc_pipeline.media import decode_timing
from qc_pipeline.temporal import validate_media

ROOT = Path(__file__).resolve().parents[1]


class MediaTests(unittest.TestCase):
    def test_decoded_vfr_pts_match_committed_manifest(self):
        for name in ["known-boundaries", "ambiguous-contact"]:
            manifest = json.loads(
                (ROOT / f"fixtures/temporal/{name}.json").read_text()
            )["media"]
            actual = decode_timing(ROOT / f"fixtures/temporal/{name}.mp4")
            for field in ["pts", "timebase", "duration_pts", "sha256"]:
                self.assertEqual(actual[field], manifest[field])
            seconds = [
                Fraction(x) * Fraction(*actual["timebase"]) for x in actual["pts"]
            ]
            self.assertEqual(
                seconds[:4],
                [
                    Fraction(0),
                    Fraction(80, 1000),
                    Fraction(200, 1000),
                    Fraction(300, 1000),
                ],
            )
            self.assertGreater(len(set(b - a for a, b in zip(seconds, seconds[1:]))), 1)
            self.assertEqual(validate_media(actual), [])

    def test_actual_dropped_frame_is_detected_against_generation_schedule(self):
        expected = json.loads(
            (ROOT / "fixtures/temporal/dropped-frame-timing.json").read_text()
        )
        decoded = decode_timing(ROOT / "fixtures/temporal/dropped-frame.mp4")
        decoded["expected_pts"] = expected["expected_pts"]
        self.assertEqual(len(decoded["pts"]), 59)
        self.assertIn("dropped", " ".join(validate_media(decoded)))


if __name__ == "__main__":
    unittest.main()
