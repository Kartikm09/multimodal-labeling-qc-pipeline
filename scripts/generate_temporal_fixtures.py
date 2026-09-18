"""Deterministic flat-shape first-person-camera simulation, no human or robot footage."""

import copy
import json
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image, ImageDraw

from qc_pipeline.media import decode_timing
from qc_pipeline.temporal import compare_boundaries, validate_case

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "fixtures/temporal"


def draw_frame(ms, ambiguous=False):
    image = Image.new("RGB", (640, 360), "#e8ecef")
    draw = ImageDraw.Draw(image)
    draw.polygon([(0, 360), (70, 80), (570, 80), (640, 360)], fill="#c1cbd2")
    draw.rectangle((60, 50, 580, 90), fill="#94a3ae")
    draw.text(
        (18, 15),
        "SYNTHETIC FIRST-PERSON SIMULATION | no captured human/robot footage",
        fill="#173341",
    )
    draw.text(
        (18, 330),
        f"Time {ms / 1000:.3f} s | arm-1 / block-1 | generated shapes",
        fill="#173341",
    )
    # Source trajectory defines phase transitions at integer seconds; ambiguous fixture adds occlusion.
    if ms < 1000:
        hand = (150 + int(100 * ms / 1000), 285 - int(65 * ms / 1000))
        block = (270, 215)
    elif ms < 2000:
        hand = (250, 220)
        block = (270, 215)
    elif ms < 3000:
        hand = (250, 220 - int(70 * (ms - 2000) / 1000))
        block = (270, 215 - int(70 * (ms - 2000) / 1000))
    elif ms < 4000:
        hand = (250 + int(150 * (ms - 3000) / 1000), 150)
        block = (270 + int(150 * (ms - 3000) / 1000), 145)
    elif ms < 5000:
        hand = (400, 150 + int(70 * (ms - 4000) / 1000))
        block = (420, 145 + int(70 * (ms - 4000) / 1000))
    else:
        hand = (400 + int(60 * (ms - 5000) / 1000), 220 + int(70 * (ms - 5000) / 1000))
        block = (420, 215)
    x, y = block
    draw.rectangle(
        (x - 18, y - 18, x + 18, y + 18), fill="#3d7b9b", outline="#183b50", width=3
    )
    x, y = hand
    draw.line((130, 360, x, y), fill="#64768b", width=36)
    draw.rectangle(
        (x - 24, y - 12, x + 3, y + 20), fill="#d2a957", outline="#5b482a", width=3
    )
    draw.line((x, y - 12, x + 25, y - 20), fill="#d2a957", width=10)
    draw.line((x + 2, y + 18, x + 27, y + 25), fill="#d2a957", width=10)
    if ambiguous and 900 <= ms <= 2400:
        draw.rectangle((235, 170, 315, 250), fill="#626c74")
        draw.text((322, 200), "occlusion", fill="#253342")
    return image


def encode(name, pts, ambiguous=False):
    output = DEST / (name + ".mp4")
    with av.open(str(output), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width = 640
        stream.height = 360
        stream.pix_fmt = "yuv420p"
        stream.time_base = Fraction(1, 1000)
        stream.codec_context.time_base = Fraction(1, 1000)
        stream.codec_context.max_b_frames = 0
        stream.options = {"crf": "24", "preset": "veryfast"}
        for tick in pts:
            frame = av.VideoFrame.from_image(draw_frame(tick, ambiguous))
            frame.pts = tick
            frame.time_base = Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return decode_timing(output)


def build():
    DEST.mkdir(exist_ok=True)
    points = []
    tick = 0
    for i in range(60):
        points.append(tick)
        tick += [80, 120, 100][i % 3]
    all_cases = []
    for name, ambiguous in [("known-boundaries", False), ("ambiguous-contact", True)]:
        media = encode(name, points, ambiguous)
        scale = Fraction(*media["timebase"])
        events = []
        for i, action in enumerate(
            ["approach", "grasp", "lift", "move", "place", "release"]
        ):
            events.append(
                {
                    "id": "e" + str(i + 1),
                    "action": action,
                    "start": int(Fraction(i, 1) / scale),
                    "end": int(Fraction(i + 1, 1) / scale)
                    if i < 5
                    else media["duration_pts"],
                    "actor": "arm-1",
                    "object": "block-1",
                    "outcome": "unknown" if ambiguous and i in [1, 2] else "successful",
                    "partial": False,
                    "occluded": ambiguous and i in [1, 2],
                    "uncertainty": "Contact hidden; human judgment needed"
                    if ambiguous and i in [1, 2]
                    else "",
                    "overlap_group": "",
                    "overlap_reason": "",
                }
            )
        case = {
            "id": name,
            "classification": "synthetic-first-person-simulation",
            "media": media,
            "events": events,
        }
        assert not validate_case(case), validate_case(case)
        (DEST / (name + ".json")).write_text(json.dumps(case, indent=2) + "\n")
        all_cases.append(case)
    dropped = encode("dropped-frame", points[:15] + points[16:])
    scale = Fraction(*dropped["timebase"])
    dropped["expected_pts"] = [int(Fraction(p, 1000) / scale) for p in points]
    (DEST / "dropped-frame-timing.json").write_text(
        json.dumps(dropped, indent=2) + "\n"
    )
    shifted = copy.deepcopy(all_cases[0])
    shifted["events"] = shifted["events"][1:2]
    shifted["events"][0]["start"] += int(Fraction(1, 10) / scale)
    shifted["events"][0]["end"] += int(Fraction(1, 10) / scale)
    truth = copy.deepcopy(all_cases[0])
    truth["events"] = truth["events"][1:2]
    (ROOT / "reports/temporal-calibration.json").write_text(
        json.dumps(
            {
                "classification": "simulated reviewer calibration",
                "known_identical": compare_boundaries(all_cases[0], all_cases[0]),
                "shifted_100ms": compare_boundaries(truth, shifted),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "Generated 2 review cases and 1 dropped-frame diagnostic from owned procedural shapes"
    )


if __name__ == "__main__":
    build()
