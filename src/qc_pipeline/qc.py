"""CSV quality checks for multimodal annotation rows."""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path


REQUIRED_COLUMNS = {"asset_id", "modality", "label", "confidence", "reviewer_notes"}


def evaluate_rows(rows: list[dict]) -> list[dict]:
    issues_by_asset: dict[str, list[str]] = defaultdict(list)
    labels_by_asset: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        asset_id = row.get("asset_id", "").strip()
        label = row.get("label", "").strip()
        labels_by_asset[asset_id].add(label)

        if not label:
            issues_by_asset[asset_id].append("missing-label")
        if not row.get("reviewer_notes", "").strip():
            issues_by_asset[asset_id].append("missing-reviewer-notes")

        try:
            confidence = float(row.get("confidence", 0))
        except ValueError:
            confidence = 0

        if confidence < 0.7:
            issues_by_asset[asset_id].append("low-confidence")

    for asset_id, labels in labels_by_asset.items():
        clean_labels = {label for label in labels if label}
        if len(clean_labels) > 1:
            issues_by_asset[asset_id].append("label-disagreement")

    return [
        {"asset_id": asset_id, "issues": sorted(set(issues))}
        for asset_id, issues in sorted(issues_by_asset.items())
        if issues
    ]


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m qc_pipeline.qc examples/annotations.csv")

    issues = evaluate_rows(read_rows(Path(sys.argv[1])))
    for item in issues:
        print(f"{item['asset_id']}: {', '.join(item['issues'])}")


if __name__ == "__main__":
    main()
