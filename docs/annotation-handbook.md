# Annotation handbook

Every label is an interval `[start, end)` in integer presentation timestamp ticks. Convert seconds
using `tick × timebase numerator / denominator`. Start is inclusive; end is exclusive. An end may
be exactly the recorded duration. The final decoded frame covers its PTS until that duration;
there is no extra frame at the duration. Reject reversed, zero-length or out-of-range intervals.

Use decoded PTS to seek and step variable-frame-rate media. The most recent frame with PTS no
later than the requested tick is displayed. Do not divide the frame index by a nominal frame rate.
For unknown real media, a timestamp gap alone is not proof of a dropped frame; our dropped-frame
check has an independently known generation schedule.

| Action | Boundary cue in this simulation |
| --- | --- |
| Approach | Gripper starts moving toward the block until contact phase |
| Grasp | Contact/closing attempt until upward motion starts |
| Lift | Upward motion until horizontal transport begins |
| Move | Horizontal transport until lowering starts |
| Place | Lowering until withdrawal begins |
| Release | Withdrawal until clip end |

Action and outcome are separate fields. `attempted` records an attempt without asserting success;
`successful`, `failed` and `unknown` state the available outcome evidence. An occluded contact does
not justify inferring a successful grasp. Mark partial actions when the clip cuts off a phase.
Explain uncertainty in words, including which cue is hidden or ambiguous.

Supply stable actor/object references. Same actor/object overlaps are invalid unless both events
share a nonempty overlap group and each has a written reason. An overlap may be defensible when
contact and lift transition gradually; the reviewer must explain it. Duplicate event IDs are rejected.

Original labels are revision zero. Saving creates a new immutable revision with reviewer, reason
and UTC timestamp. Concurrent stale edits return HTTP 409, preserving both the original and the
latest accepted review. SQLite triggers prohibit update/delete on revision and ranking rows.
These are application integrity controls, not tamper-proof protection against an administrator
who can replace the database. Preserve originals separately when sharing exports.

Compare two distinct revisions and choose left/right/tie with written evidence. Ranking is a human
judgment; it does not create a ground-truth label automatically. Use a reviewer label that identifies
simulated exercises as simulated. Do not include personal data in this local synthetic demo.

JSON is the canonical export. The CVAT XML 1.1 subset uses frame tags with `event_json`, `provenance`
and `timebase` attributes. The frame is the event's starting decoded frame; subframe end ticks stay
in `event_json`. Our importer requires supplied media metadata and rejects mismatched frames,
labels, provenance and timebase, oversized XML and DTD/entity declarations. This subset was round-
tripped locally; a live CVAT import remains unrun.
