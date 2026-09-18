"""Temporal review of synthetic clips. Intervals are half-open integer PTS ticks."""

from __future__ import annotations

import bisect
import json
import xml.etree.ElementTree as ET
from fractions import Fraction

ACTIONS = {"approach", "grasp", "lift", "move", "place", "release"}
OUTCOMES = {"attempted", "successful", "failed", "unknown"}


def _integer(value):
    return type(value) is int


def validate_media(media):
    errors = []
    if not isinstance(media, dict):
        return ["media must be an object"]
    tb = media.get("timebase")
    pts = media.get("pts")
    end = media.get("duration_pts")
    if (
        not isinstance(tb, list)
        or len(tb) != 2
        or not all(_integer(x) and x > 0 for x in tb)
    ):
        errors.append(
            "timebase must contain positive integer numerator and denominator"
        )
    if (
        not isinstance(pts, list)
        or not pts
        or len(pts) > 100000
        or not all(_integer(x) and x >= 0 for x in pts)
    ):
        return errors + [
            "pts must contain bounded nonnegative integer decoded timestamps"
        ]
    if any(b <= a for a, b in zip(pts, pts[1:])):
        errors.append("pts must be strictly increasing")
    if not _integer(end) or end <= pts[-1]:
        errors.append("duration_pts must exceed last presentation timestamp")
    expected = media.get("expected_pts")
    if expected is not None:
        if not isinstance(expected, list) or not all(_integer(x) for x in expected):
            errors.append("invalid expected_pts")
        elif set(expected) - set(pts):
            errors.append("dropped frames relative to known fixture timestamps")
    return errors


def validate_case(case):
    if not isinstance(case, dict):
        return ["case must be an object"]
    errors = validate_media(case.get("media"))
    if not isinstance(case.get("id"), str) or not case["id"].strip():
        errors.append("missing case id")
    if case.get("classification") != "synthetic-first-person-simulation":
        errors.append("unsupported provenance classification")
    events = case.get("events")
    if not isinstance(events, list) or len(events) > 1000:
        return errors + ["events must be a bounded list"]
    media = case.get("media") if isinstance(case.get("media"), dict) else {}
    end = media.get("duration_pts")
    seen = set()
    valid = []
    first = (
        media.get("pts", [0])[0]
        if isinstance(media.get("pts"), list)
        and media["pts"]
        and _integer(media["pts"][0])
        else 0
    )
    for i, event in enumerate(events):
        prefix = f"event {i}: "
        if not isinstance(event, dict):
            errors.append(prefix + "must be an object")
            continue
        identifier = event.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            errors.append(prefix + "missing event id")
        elif identifier in seen:
            errors.append(prefix + "duplicate event id")
        else:
            seen.add(identifier)
        if not isinstance(event.get("action"), str) or event["action"] not in ACTIONS:
            errors.append(prefix + "unknown action")
        if (
            not isinstance(event.get("outcome"), str)
            or event["outcome"] not in OUTCOMES
        ):
            errors.append(prefix + "missing or unknown outcome")
        for key in ["actor", "object"]:
            if not isinstance(event.get(key), str) or not event[key].strip():
                errors.append(prefix + "missing " + key)
        for key in ["partial", "occluded"]:
            if type(event.get(key)) is not bool:
                errors.append(prefix + key + " must be boolean")
        for key in ["uncertainty", "overlap_group", "overlap_reason"]:
            if not isinstance(event.get(key), str) or len(event[key]) > 2000:
                errors.append(prefix + "invalid " + key)
        start, stop = event.get("start"), event.get("end")
        if (
            not all(_integer(x) for x in [start, stop, end])
            or not first <= start < stop <= end
        ):
            errors.append(prefix + "reversed or out-of-range interval")
            continue
        valid.append(event)
    for i, a in enumerate(valid):
        for b in valid[i + 1 :]:
            same = (a.get("actor"), a.get("object")) == (
                b.get("actor"),
                b.get("object"),
            )
            overlap = max(a["start"], b["start"]) < min(a["end"], b["end"])
            intended = (
                bool(a.get("overlap_group"))
                and a.get("overlap_group") == b.get("overlap_group")
                and all(
                    isinstance(x.get("overlap_reason"), str)
                    and x["overlap_reason"].strip()
                    for x in [a, b]
                )
            )
            if same and overlap and not intended:
                errors.append(
                    "invalid overlap: " + str(a.get("id")) + " / " + str(b.get("id"))
                )
    return errors


def frame_at(media, tick):
    errors = validate_media(media)
    if errors:
        raise ValueError("; ".join(errors))
    if not _integer(tick) or tick < media["pts"][0] or tick >= media["duration_pts"]:
        raise ValueError("timestamp outside clip")
    return bisect.bisect_right(media["pts"], tick) - 1


def compare_boundaries(truth, predicted):
    for item in [truth, predicted]:
        errors = validate_case(item)
        if errors:
            raise ValueError("; ".join(errors))
    if truth["id"] != predicted["id"] or truth["media"] != predicted["media"]:
        raise ValueError("different media cannot be compared")
    choices = []
    for i, a in enumerate(truth["events"]):
        for j, b in enumerate(predicted["events"]):
            if tuple(a[k] for k in ["action", "actor", "object"]) != tuple(
                b[k] for k in ["action", "actor", "object"]
            ):
                continue
            intersection = max(0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
            union = max(a["end"], b["end"]) - min(a["start"], b["start"])
            iou = intersection / union
            if iou >= 0.1:
                choices.append((-iou, a["id"], b["id"], i, j))
    used_a = set()
    used_b = set()
    matches = []
    scale = Fraction(*truth["media"]["timebase"])
    for minus_iou, _, __, i, j in sorted(choices):
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        a = truth["events"][i]
        b = predicted["events"][j]
        error = float(
            (abs(a["start"] - b["start"]) + abs(a["end"] - b["end"])) * scale / 2
        )
        matches.append(
            {
                "truth_id": a["id"],
                "prediction_id": b["id"],
                "temporal_iou": -minus_iou,
                "boundary_error_seconds": error,
                "outcome_agrees": a["outcome"] == b["outcome"],
            }
        )
    count = len(matches)
    return {
        "matching": "greedy descending IoU >= 0.1; exact action/actor/object; IDs break ties; one-to-one",
        "matched": count,
        "false_positive": len(predicted["events"]) - count,
        "false_negative": len(truth["events"]) - count,
        "precision": count / len(predicted["events"]) if predicted["events"] else None,
        "recall": count / len(truth["events"]) if truth["events"] else None,
        "mean_boundary_error_seconds": sum(x["boundary_error_seconds"] for x in matches)
        / count
        if count
        else None,
        "mean_temporal_iou": sum(x["temporal_iou"] for x in matches) / count
        if count
        else None,
        "matches": matches,
    }


def export_cvat(case):
    """CVAT 1.1 frame tags; explicit PTS attributes preserve subframe/VFR intervals."""
    errors = validate_case(case)
    if errors:
        raise ValueError("; ".join(errors))
    root = ET.Element("annotations")
    ET.SubElement(root, "version").text = "1.1"
    meta = ET.SubElement(root, "meta")
    task = ET.SubElement(meta, "task")
    for key, value in [
        ("id", "0"),
        ("name", case["id"]),
        ("size", str(len(case["media"]["pts"]))),
        ("mode", "annotation"),
        ("overlap", "0"),
        ("start_frame", "0"),
        ("stop_frame", str(len(case["media"]["pts"]) - 1)),
        ("frame_filter", ""),
    ]:
        ET.SubElement(task, key).text = value
    labels = ET.SubElement(task, "labels")
    for action in sorted(ACTIONS):
        label = ET.SubElement(labels, "label")
        ET.SubElement(label, "name").text = action
        attrs = ET.SubElement(label, "attributes")
        for key in ["event_json", "provenance", "timebase"]:
            attr = ET.SubElement(attrs, "attribute")
            for k, v in [
                ("name", key),
                ("mutable", "False"),
                ("input_type", "text"),
                ("default_value", ""),
                ("values", ""),
            ]:
                ET.SubElement(attr, k).text = v
    images = {}
    for event in case["events"]:
        frame = frame_at(case["media"], event["start"])
        if frame not in images:
            images[frame] = ET.SubElement(
                root,
                "image",
                id=str(frame),
                name=f"frame_{frame:06d}.png",
                width="640",
                height="360",
            )
        tag = ET.SubElement(
            images[frame], "tag", label=event["action"], source="manual"
        )
        for key, value in [
            ("event_json", json.dumps(event, sort_keys=True)),
            ("provenance", case["classification"]),
            ("timebase", json.dumps(case["media"]["timebase"])),
        ]:
            ET.SubElement(tag, "attribute", name=key).text = value
    return ET.tostring(root, encoding="unicode")


def import_cvat(xml, media):
    if (
        len(xml.encode()) > 1000000
        or "<!DOCTYPE" in xml.upper()
        or "<!ENTITY" in xml.upper()
    ):
        raise ValueError("unsafe XML")
    try:
        root = ET.fromstring(xml)
        if root.tag != "annotations" or root.findtext("version") != "1.1":
            raise ValueError("unsupported CVAT document")
        case = {
            "id": root.findtext("meta/task/name"),
            "classification": "synthetic-first-person-simulation",
            "media": media,
            "events": [],
        }
        for image in root.findall("image"):
            for tag in image.findall("tag"):
                attrs = {a.get("name"): a.text for a in tag.findall("attribute")}
                event = json.loads(attrs["event_json"])
                if (
                    attrs["provenance"] != case["classification"]
                    or json.loads(attrs["timebase"]) != media["timebase"]
                ):
                    raise ValueError("provenance/timebase mismatch")
                if (
                    int(image.attrib["id"]) != frame_at(media, event["start"])
                    or tag.attrib["label"] != event["action"]
                ):
                    raise ValueError("frame/label mismatch")
                case["events"].append(event)
        errors = validate_case(case)
        if errors:
            raise ValueError("; ".join(errors))
        return case
    except (ET.ParseError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid CVAT annotations") from error
