"""Independent boundary expectations; all examples and reviewers are synthetic."""

import copy
import tempfile
import unittest
from pathlib import Path

from qc_pipeline.temporal import (
    validate_case,
    compare_boundaries,
    frame_at,
    export_cvat,
    import_cvat,
)
from qc_pipeline.review_store import ReviewStore


def case():
    return {
        "id": "clip-1",
        "classification": "synthetic-first-person-simulation",
        "media": {
            "timebase": [1, 1000],
            "pts": [0, 100, 250, 300, 500],
            "duration_pts": 600,
        },
        "events": [
            {
                "id": "e1",
                "action": "grasp",
                "start": 100,
                "end": 300,
                "actor": "arm-1",
                "object": "block-1",
                "outcome": "attempted",
                "partial": False,
                "occluded": False,
                "uncertainty": "contact ambiguous",
                "overlap_group": "",
                "overlap_reason": "",
            }
        ],
    }


class TemporalTests(unittest.TestCase):
    def test_vfr_frame_uses_decoded_pts_and_final_frame(self):
        self.assertEqual(frame_at(case()["media"], 249), 1)
        self.assertEqual(frame_at(case()["media"], 250), 2)
        self.assertEqual(frame_at(case()["media"], 599), 4)
        with self.assertRaises(ValueError):
            frame_at(case()["media"], 600)

    def test_valid_partial_and_final_interval(self):
        value = case()
        value["events"][0].update(start=500, end=600, partial=True)
        self.assertEqual(validate_case(value), [])

    def test_reversed_out_of_range_and_duplicate_ids_are_rejected(self):
        for start, end in [(300, 100), (100, 100), (-1, 100), (500, 601)]:
            value = case()
            value["events"][0].update(start=start, end=end)
            self.assertTrue(validate_case(value), (start, end))
        value = case()
        value["events"] *= 2
        self.assertIn("duplicate event id", " ".join(validate_case(value)))

    def test_invalid_overlap_and_documented_overlap(self):
        value = case()
        other = copy.deepcopy(value["events"][0])
        other.update(id="e2", action="lift", start=250, end=500)
        value["events"].append(other)
        self.assertIn("overlap", " ".join(validate_case(value)))
        for row in value["events"]:
            row.update(
                overlap_group="contact-lift",
                overlap_reason="Gradual contact boundary, simulated reviewer judgment",
            )
        self.assertEqual(validate_case(value), [])

    def test_nonfinite_bool_and_missing_fields_rejected(self):
        for bad in [float("nan"), True, "100"]:
            value = case()
            value["events"][0]["start"] = bad
            self.assertTrue(validate_case(value))
        value = case()
        del value["events"][0]["outcome"]
        self.assertTrue(validate_case(value))

    def test_duplicate_or_reversed_pts_and_dropped_frames(self):
        for pts in [[0, 100, 100], [0, 250, 100]]:
            value = case()
            value["media"]["pts"] = pts
            self.assertTrue(validate_case(value))
        value = case()
        value["media"]["expected_pts"] = [0, 100, 200, 250, 300, 500]
        self.assertIn("dropped", " ".join(validate_case(value)))

    def test_shifted_boundaries_have_independent_metrics(self):
        truth = case()
        pred = copy.deepcopy(truth)
        pred["events"][0].update(start=250, end=500)
        report = compare_boundaries(truth, pred)
        self.assertAlmostEqual(report["mean_boundary_error_seconds"], 0.175)
        self.assertAlmostEqual(report["mean_temporal_iou"], 0.125)
        self.assertEqual(report["matched"], 1)

    def test_unmatched_labels_do_not_inflate_overlap(self):
        pred = case()
        pred["events"][0]["action"] = "release"
        report = compare_boundaries(case(), pred)
        self.assertEqual(report["matched"], 0)
        self.assertEqual(report["precision"], 0)
        self.assertIsNone(report["mean_boundary_error_seconds"])

    def test_cvat_frame_tag_round_trip_keeps_ticks_and_uncertainty(self):
        value = case()
        xml = export_cvat(value)
        self.assertIn("<annotations>", xml)
        self.assertEqual(import_cvat(xml, value["media"]), value)

    def test_malformed_nested_types_are_validation_errors(self):
        for bad in [None, [], True]:
            value = case()
            value["media"] = bad
            self.assertTrue(validate_case(value))
            for field in ["action", "outcome", "actor", "overlap_reason"]:
                value = case()
                value["events"][0][field] = bad
                self.assertTrue(validate_case(value))

    def test_events_before_first_presentation_timestamp_rejected(self):
        value = case()
        value["media"]["pts"] = [100, 250, 300, 500]
        value["events"][0]["start"] = 0
        self.assertTrue(validate_case(value))

    def test_xml_entity_and_oversized_payloads_rejected(self):
        for xml in [
            '<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><annotations/>',
            "x" * 1_000_001,
        ]:
            with self.assertRaises(ValueError):
                import_cvat(xml, case()["media"])


class ReviewStoreTests(unittest.TestCase):
    def test_original_is_preserved_history_append_only_and_conflict_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = ReviewStore(Path(tmp) / "reviews.sqlite")
            s.create(case())
            revised = case()
            revised["events"][0]["outcome"] = "successful"
            s.revise(
                "clip-1",
                revised,
                reviewer="simulated-reviewer",
                reason="Object lifted visibly",
                expected_revision=0,
            )
            self.assertEqual(
                s.history("clip-1")[0]["document"]["events"][0]["outcome"], "attempted"
            )
            self.assertEqual(s.latest("clip-1")["revision"], 1)
            with self.assertRaises(ValueError):
                s.revise(
                    "clip-1",
                    case(),
                    reviewer="simulated-reviewer",
                    reason="stale",
                    expected_revision=0,
                )
            self.assertEqual(len(s.history("clip-1")), 2)

    def test_revision_and_ranking_tables_enforce_append_only(self):
        import sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.sqlite"
            s = ReviewStore(path)
            s.create(case())
            revised = case()
            revised["events"][0]["outcome"] = "successful"
            s.revise(
                "clip-1",
                revised,
                reviewer="simulated",
                reason="Visible lift",
                expected_revision=0,
            )
            s.rank("clip-1", 0, 1, "right", "Better distinction of attempt and outcome")
            self.assertEqual(len(s.rankings("clip-1")), 1)
            with sqlite3.connect(path) as db:
                for query in [
                    "DELETE FROM revisions",
                    'UPDATE revisions SET reason="changed"',
                    "DELETE FROM rankings",
                    'UPDATE rankings SET evidence="changed"',
                ]:
                    with self.assertRaises(sqlite3.IntegrityError):
                        db.execute(query)
            with self.assertRaises(ValueError):
                s.rank("clip-1", False, 1, "right", "Boolean is not revision zero")

    def test_invalid_revision_and_evidenceless_ranking_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = ReviewStore(Path(tmp) / "reviews.sqlite")
            s.create(case())
            bad = case()
            bad["events"][0]["end"] = 0
            with self.assertRaises(ValueError):
                s.revise(
                    "clip-1",
                    bad,
                    reviewer="simulated-reviewer",
                    reason="bad",
                    expected_revision=0,
                )
            with self.assertRaises(ValueError):
                s.rank("clip-1", 0, 0, "tie", "")
            self.assertEqual(len(s.history("clip-1")), 1)


if __name__ == "__main__":
    unittest.main()
