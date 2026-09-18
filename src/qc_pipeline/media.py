"""Read actual decoded presentation timestamps, never frame-index / nominal-fps."""

import hashlib
from pathlib import Path


def decode_timing(path):
    import av

    path = Path(path)
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        frames = list(container.decode(stream))
        if not frames or any(frame.pts is None for frame in frames):
            raise ValueError("video lacks decoded presentation timestamps")
        tb = frames[0].time_base
        if any(frame.time_base != tb for frame in frames):
            raise ValueError("changing frame timebase")
        if stream.duration is None:
            raise ValueError("explicit stream duration required")
        end = (stream.start_time or 0) + stream.duration
        duration = int(end * stream.time_base / tb)
        return {
            "timebase": [tb.numerator, tb.denominator],
            "pts": [frame.pts for frame in frames],
            "duration_pts": duration,
            "width": stream.width,
            "height": stream.height,
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "decoder": "PyAV " + av.__version__,
            "classification": "synthetic-first-person-simulation",
        }
