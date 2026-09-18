# Multimodal Labeling QC Pipeline

Quality-control pipeline for AI annotation and labeling projects across text, image, video, and UI tasks.

This portfolio project demonstrates how an AI trainer or annotation QA reviewer can validate labels, confidence scores, annotator notes, and disagreement patterns before data is sent back into a training loop.

## What It Checks

- Missing labels.
- Low-confidence annotations.
- Empty reviewer notes.
- Conflicting labels for the same asset.
- Domain-specific QA flags.
- Export-ready summary reports.

## Quick Start

```bash
PYTHONPATH=src python3 -m qc_pipeline.qc examples/annotations.csv
```

## n8n Workflow

The `workflows/n8n_annotation_qc.json` file is a public-safe workflow blueprint showing how annotation rows could move through:

1. Intake.
2. QC scoring.
3. Reviewer routing.
4. Summary report.

It is a blueprint, not a live credentialed workflow.

## Skills Demonstrated

- Data annotation QA
- Multimodal evaluation
- Labeling pipeline design
- Python validation
- n8n workflow thinking
- Error taxonomy design
- Reviewer operations


## Local action-boundary review

The temporal extension reviews **procedurally generated first-person-camera simulations**.
No clip is captured human/robot footage. Original generated labels and subsequent human or
explicitly simulated reviews are stored separately. The CSV QC and n8n blueprint remain available.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install pip==26.2.1
.venv/bin/python -m pip install -r requirements-media.txt
make verify PYTHON=.venv/bin/python
make demo PYTHON=.venv/bin/python
```

Open `http://127.0.0.1:8765`. Select a clip, play or step decoded frames, edit one event, and
write evidence before saving a new revision. Pairwise rankings also require written evidence.
The local `reviews.sqlite` store is ignored by Git. This is a single-user loopback tool;
it has no remote accounts, provider integration, or production deployment.

`make media PYTHON=.venv/bin/python` regenerates the three small owned simulation clips and
calibration report with pinned PyAV/Pillow. It is optional: committed clips are ready to review.
Regeneration can change encoded bytes across codec builds; decoded times are validated explicitly.

```bash
npm ci --ignore-scripts
npx playwright install chromium
npm test
```

Browser checks use Playwright 1.61.1 and a fresh temporary SQLite store. They test actual playback,
VFR stepping, invalid intervals, revisions, exports, ranking, and empty/added-event recovery.
Real screenshots are written to `reports/ui-chromium-<platform>-<width>x<height>.png` at
1920×1080, 1440×900 and 390×844. These are execution captures, not approved pixel-diff baselines.

- [Data card and provenance](docs/data-card.md)
- [Annotation handbook](docs/annotation-handbook.md)
- [Calibration, matching and limits](docs/calibration.md)
- [Local review architecture and verification](docs/review-design.md)

JSON export preserves exact PTS ticks. CVAT XML 1.1 frame tags carry the full event as a documented
attribute; our bounded importer round-trips this subset. A live CVAT application import has not
been executed, so application compatibility beyond that tested subset remains unverified.
