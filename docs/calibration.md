# Calibration and measurement

`reports/temporal-calibration.json` is computed from known synthetic trajectories and explicitly
simulated reviewer perturbations. It is not a human inter-annotator study.

Match only equal action/actor/object triples. Candidate pairs require temporal intersection over
union (IoU) ≥ 0.1. Greedily select descending IoU, break ties by IDs, and use each event once.
Boundary error is the mean absolute start/end difference multiplied by the rational timebase.
Report unmatched predictions as false positives and unmatched truths as false negatives. Average
boundary error and IoU are null if no pairs match, so missing labels cannot silently score zero error.
This simple matching rule can differ from globally optimal assignment; it is stated in every report.

The known identical case has zero boundary error and IoU 1. The simulated 100ms shift for a one-
second grasp interval has boundary error 0.1 seconds and IoU 0.9/1.1 ≈ 0.81818. A separate unit test
uses intervals [100,300) and [250,500) with timebase 1/1000, independently asserting error 0.175s
and IoU 50/400 = 0.125. These are deterministic fixture metrics, not model improvements.

Calibration exercise: first inspect known-boundaries at the approach/grasp transition. Then inspect
ambiguous-contact around 0.9–2.4s. The occluder obscures success evidence, so reviewers should
record uncertainty instead of copying successful outcomes from the unobscured clip. A partial
release ending at clip duration is valid; a release ending beyond duration is invalid. Intentional
overlap needs a shared group and written rationale; ordinary overlapping duplicates fail validation.

The unit/API/browser suites cover shifted boundaries, invalid and reversed intervals, duplicate
IDs, overlap decisions, partial actions, dropped frames, VFR stepping, original/revised history,
optimistic conflicts, and JSON/CVAT subset round trips. Browser captures are real executions.
They are not evidence of annotation agreement, semantic correctness of every reviewer decision,
or compatibility with untested third-party platforms.
