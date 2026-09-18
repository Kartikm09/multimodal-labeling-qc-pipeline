import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from qc_pipeline.review_server import create_server


class ReviewAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = create_server(Path(self.tmp.name) / "reviews.sqlite", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def request(self, path, payload=None, headers=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        request = Request(
            self.base + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read()
        except HTTPError as error:
            return error.code, error.read()

    def test_actual_api_revisions_conflicts_and_exports(self):
        path = "/api/cases/known-boundaries"
        code, body = self.request(path)
        self.assertEqual(code, 200)
        original = json.loads(body)["history"][0]["document"]
        edited = copy.deepcopy(original)
        edited["events"][1]["outcome"] = "attempted"
        request = {
            "document": edited,
            "reviewer": "simulated-reviewer",
            "reason": "Contact observed; success remains separate",
            "expected_revision": 0,
        }
        self.assertEqual(self.request(path + "/revisions", request)[0], 201)
        self.assertEqual(self.request(path + "/revisions", request)[0], 409)
        history = json.loads(self.request(path)[1])["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["document"], original)
        self.assertEqual(json.loads(self.request(path + "/export.json")[1]), edited)
        self.assertIn(b"<annotations>", self.request(path + "/export.xml")[1])
        self.assertEqual(
            self.request(
                path + "/rankings",
                {
                    "left": 0,
                    "right": 1,
                    "preference": "right",
                    "evidence": "Distinguishes outcome from attempt",
                },
            )[0],
            201,
        )

    def test_media_supports_seekable_byte_ranges(self):
        code, body = self.request(
            "/media/known-boundaries.mp4", headers={"Range": "bytes=0-15"}
        )
        self.assertEqual(code, 206)
        self.assertEqual(len(body), 16)
        self.assertEqual(
            self.request(
                "/media/known-boundaries.mp4", headers={"Range": "bytes=999999999-"}
            )[0],
            416,
        )
        self.assertEqual(
            self.request(
                "/media/known-boundaries.mp4", headers={"Range": "bytes=0-1,5-6"}
            )[0],
            416,
        )

    def test_invalid_input_foreign_origin_and_unknown_path(self):
        path = "/api/cases/known-boundaries"
        original = json.loads(self.request(path)[1])["history"][0]["document"]
        original["events"][0]["end"] = -1
        request = {
            "document": original,
            "reviewer": "simulated",
            "reason": "invalid",
            "expected_revision": 0,
        }
        self.assertEqual(self.request(path + "/revisions", request)[0], 400)
        self.assertEqual(
            self.request(
                path + "/revisions", request, {"Origin": "https://foreign.example"}
            )[0],
            403,
        )
        self.assertEqual(
            self.request(path, headers={"Host": "foreign.example"})[0], 403
        )
        self.assertEqual(self.request("/../../README.md")[0], 404)
        self.assertEqual(len(json.loads(self.request(path)[1])["history"]), 1)


if __name__ == "__main__":
    unittest.main()
