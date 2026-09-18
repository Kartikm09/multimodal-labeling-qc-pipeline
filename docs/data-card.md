# Synthetic temporal review data card

Created 18 September 2026 for independent portfolio verification. Existing repository MIT license
is preserved. The new generated shapes and metadata are original repository work under that license.
No stock media, faces, personal recordings, client traces, or captured robot footage are included.

`scripts/generate_temporal_fixtures.py` draws a stylized gripper, block and work surface from a
fixed virtual first-person camera. It encodes 60 frames with alternating 80/120/100ms source
spacing using PyAV 18.1.0 and Pillow 12.3.0. The MP4 is decoded again; its actual stream timebase,
PTS sequence, explicit end duration, dimensions, decoder version and SHA-256 are committed in JSON.
Nominal FPS is never used to calculate review boundaries.

- `known-boundaries`: six deterministic trajectory phases. Original labels are generated from
  known motion phases, not claimed human annotation or captured physical success.
- `ambiguous-contact`: the same movement with a generated occluder covering contact/lift. Grasp
  and lift outcomes are unknown. This deliberately requires reviewer judgment.
- `dropped-frame`: one source frame is omitted. The separate timing file supplies the known
  expected schedule so QC can detect the missing timestamp. It is a negative diagnostic fixture.

Actor `arm-1` and object `block-1` are synthetic references. There is no human demographic data.
The renderer is intentionally simple and cannot establish annotation performance on natural video,
robotics transfer, model quality, or a reviewer's professional proficiency.

Regenerate with `make media PYTHON=.venv/bin/python`. Tests independently decode all clips and
check the nonuniform timestamps and the known dropped frame. MP4 byte identity is not promised
across codec/library platforms; record the actual SHA and decoded timing when regenerating.
