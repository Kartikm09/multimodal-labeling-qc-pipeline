"""Local SQLite append-only synthetic annotation review history."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .temporal import validate_case


class ReviewStore:
    def __init__(self, path):
        self.path = path
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS revisions(case_id TEXT, revision INTEGER, document TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL, created TEXT NOT NULL, PRIMARY KEY(case_id,revision));
            CREATE TABLE IF NOT EXISTS rankings(id INTEGER PRIMARY KEY, case_id TEXT, left_revision INTEGER, right_revision INTEGER, preference TEXT, evidence TEXT, created TEXT);
            CREATE TRIGGER IF NOT EXISTS no_revision_update BEFORE UPDATE ON revisions BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_revision_delete BEFORE DELETE ON revisions BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_ranking_update BEFORE UPDATE ON rankings BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
            CREATE TRIGGER IF NOT EXISTS no_ranking_delete BEFORE DELETE ON rankings BEGIN SELECT RAISE(ABORT,'history is append-only'); END;
            """)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, document):
        errors = validate_case(document)
        if errors:
            raise ValueError("; ".join(errors))
        with self._connect() as db:
            db.execute(
                "INSERT INTO revisions VALUES (?,?,?,?,?,?)",
                (
                    document["id"],
                    0,
                    json.dumps(document, sort_keys=True),
                    "synthetic-fixture",
                    "Original generated labels",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def history(self, case_id):
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM revisions WHERE case_id=? ORDER BY revision", (case_id,)
            ).fetchall()
        return [{**dict(row), "document": json.loads(row["document"])} for row in rows]

    def latest(self, case_id):
        history = self.history(case_id)
        if not history:
            raise ValueError("unknown case")
        return history[-1]

    def revise(self, case_id, document, *, reviewer, reason, expected_revision):
        errors = validate_case(document)
        if errors or document.get("id") != case_id:
            raise ValueError("; ".join(errors) or "case id mismatch")
        if (
            type(expected_revision) is not int
            or not isinstance(reviewer, str)
            or not isinstance(reason, str)
            or not reviewer.strip()
            or not reason.strip()
            or max(len(reviewer), len(reason)) > 2000
        ):
            raise ValueError("reviewer and bounded evidence required")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM revisions WHERE case_id=? ORDER BY revision DESC LIMIT 1",
                (case_id,),
            ).fetchone()
            if row is None or row["revision"] != expected_revision:
                raise ValueError("stale review revision")
            original = json.loads(row["document"])
            if (
                original["media"] != document["media"]
                or original["classification"] != document["classification"]
            ):
                raise ValueError("media and provenance are immutable")
            db.execute(
                "INSERT INTO revisions VALUES (?,?,?,?,?,?)",
                (
                    case_id,
                    expected_revision + 1,
                    json.dumps(document, sort_keys=True),
                    reviewer,
                    reason,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return self.latest(case_id)

    def rank(self, case_id, left, right, preference, evidence):
        revisions = {x["revision"] for x in self.history(case_id)}
        if (
            type(left) is not int
            or type(right) is not int
            or left not in revisions
            or right not in revisions
            or left == right
            or not isinstance(preference, str)
            or preference not in {"left", "right", "tie"}
            or not isinstance(evidence, str)
            or not evidence.strip()
            or len(evidence) > 2000
        ):
            raise ValueError(
                "distinct revisions, preference and written evidence required"
            )
        with self._connect() as db:
            db.execute(
                "INSERT INTO rankings(case_id,left_revision,right_revision,preference,evidence,created) VALUES (?,?,?,?,?,?)",
                (
                    case_id,
                    left,
                    right,
                    preference,
                    evidence,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def rankings(self, case_id):
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM rankings WHERE case_id=? ORDER BY id", (case_id,)
            ).fetchall()
        return [dict(row) for row in rows]
