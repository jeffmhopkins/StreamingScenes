"""Renders the demo frame by frame on the engine's held clock, for a machine too slow to
record it live.

It holds JStream's media clock (`clock.hold`, ADR-0169), then for each frame fires the
shot list's events that are due, steps the clock by one frame and saves a snapshot. So
the engine itself plays every glide, the feed's motion and the sky's warp ramp, at the
frame's exact time, however long a frame takes to draw. The shot list is drive.py's.
Snapshots are at most 1280 px wide, so the frames are 1280 x 720.

A stopped run can't resume, since the scene's time is the engine's: start again with
an empty frames dir.

    python3 render_frames.py <frames dir> [fps]
    ffmpeg -framerate 30 -i <frames dir>/f%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p cockpit-demo.mp4
"""
import os
import sys
import time

from drive_events import END, EVENTS
from mcp import init, op, snap

if len(sys.argv) < 2:
    sys.exit(__doc__)
OUT = sys.argv[1]
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
os.makedirs(OUT, exist_ok=True)


def fire(vid, preset, warp):
    if vid:
        e = {"type": "scene.switch", "scene_id": vid}
        if preset:
            e["preset_id"] = preset
        op(e)
    if warp is not None:
        op({"type": "source.set_settings", "source_id": "l_env", "patch": {"warp": warp}})


init()
op({"type": "source.set_settings", "source_id": "l_env", "patch": {"warp": 0.0}})
op({"type": "scene.switch", "scene_id": "cockpit"})
time.sleep(2)
_, ok = op({"type": "clock.hold"})
if not ok:
    sys.exit("the clock wasn't held")
n = int(END / 1000 * FPS)
pending = [e for e in EVENTS if e[0] > 0]
t0 = time.time()
stepped = 0
try:
    for i in range(n):
        t_ms = round(i * 1000 / FPS)
        if t_ms > stepped:
            _, ok = op({"type": "clock.step", "ms": t_ms - stepped})
            if not ok:
                sys.exit("step failed")
            stepped = t_ms
        while pending and pending[0][0] <= t_ms:
            fire(*pending.pop(0)[1:])
        path = os.path.join(OUT, f"f{i:04d}.png")
        if not snap(path):
            sys.exit(f"snapshot {i} failed")
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"{i + 1}/{n}  {el / (i + 1):.2f} s a frame", flush=True)
finally:
    op({"type": "clock.release"})
print("done", round(time.time() - t0))
