# Local review design and verification

The existing CSV QC remains unchanged. `temporal.py` owns media/event validation and deterministic
matching; `review_store.py` owns append-only revisions and optimistic concurrency; `review_server.py`
serves a fixed loopback API and an HTML/JavaScript interface. `media.py` decodes real PTS using PyAV.

A standard-library HTTP server is adequate for an offline single-user synthetic tool. It is bound
to 127.0.0.1, accepts only its exact Host, checks browser Origin for writes, requires JSON and limits
body size. Static files and case IDs use explicit allowlists. There is no claim of tenant isolation,
remote authentication, TLS termination or production hardening. The frontend renders supplied
review text with textContent rather than HTML interpolation.

Independent review caught empty/new-event revisions crashing the original draft UI. The API's
valid empty-label state now renders an explicit empty state and disables event editing; newly added
IDs display “Added in review.” Frame controls safely ignore input while data is loading. Browser
regressions exercise both cases. Original/revised data remain available through the history API.

Actual browser stepping exposed missing byte-range responses on the MP4 endpoint: seeking
returned to frame zero. The server now supports bounded single byte ranges and returns 416
for invalid ranges. Both an API regression and real decoded-frame stepping checks verify the fix.

The original README quickstart omitted PYTHONPATH for the src layout and failed in a clean clone.
The command now includes `PYTHONPATH=src`. The existing CSV API and CLI behavior are retained.

`make verify` runs unit tests, actual loopback API requests and real video decoding. `npm test` runs
Chromium playback/review recovery and writes real viewport captures. CI runs both on Ubuntu with
Playwright pinned to 1.61.1. CI uses Python 3.12; setup pins PyAV18.1.0 and Pillow12.3.0.
Public fixture regeneration is reproducible in timing and semantics, with codec byte differences
explicitly allowed and revalidated rather than covered up with snapshot updates.

Current source references (18 September 2026):
- [CVAT XML format](https://docs.cvat.ai/docs/manual/advanced/formats/format-cvat/)
- [PyAV time bases](https://pyav.org/docs/stable/api/time.html)
- [FFprobe timestamp inspection](https://ffmpeg.org/ffprobe.html)
- [Playwright screenshots](https://playwright.dev/docs/test-snapshots)

No licensed external clips, model provider calls, paid services or deployment are involved.
