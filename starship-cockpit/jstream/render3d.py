"""Renders the 3D-layered cockpit (build_cockpit3d.py) frame by frame on JStream's held
clock (`clock.hold` / `clock.step`, JStream ADR-0169), for a machine too slow to
composite it live.

Each frame fires the events that are due, steps the engine's clock by one frame and
saves a snapshot, so the camera glides and the item transitions land on exact frames
however long a frame takes. The pages run on their own clock, so serve them with
slowserve.py slowed to match: SLOW = (seconds a frame takes) x fps, about 105 on a
CPU-only machine at 30 fps.

    python3 render3d.py <frames dir> [fps]
    ffmpeg -framerate 30 -i <frames dir>/f%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p out.mp4
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                                "cockpit-3d", "jstream"))
from mcp import init, op, snap  # noqa: E402  (cockpit-3d's client returns snap's success)

# (ms, "cam", shot, preset) moves the camera; (ms, "fx", state) switches the cockpit's
# effects (a build_cockpit.py variant) and its sky with it.
EVENTS = [
    (0, "fx", "cruise_deep"),
    (1500, "cam", "ship_left", "glide_long"),
    (3000, "fx", "scan_deep"),
    (5000, "cam", "ship_seat", "glide"),
    (6500, "fx", "warp_deep"),
    (7000, "cam", "ship_window", "glide_long"),
    (11000, "fx", "hold_nebula"),
    (11600, "fx", "arrive_nebula"),
    (12000, "cam", "ship", "glide_long"),
]
END = float(os.environ.get("END", "15500"))

if len(sys.argv) < 2:
    sys.exit(__doc__)
OUT = sys.argv[1]
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
os.makedirs(OUT, exist_ok=True)


def fire(ev):
    if ev[1] == "cam":
        op({"type": "scene.switch", "scene_id": ev[2], "preset_id": ev[3]})
    else:
        op({"type": "scene.set_keyframe", "scene_id": "cockpit", "keyframe_id": ev[2]})
        op({"type": "scene.set_keyframe", "scene_id": "sky", "keyframe_id": "sky_" + ev[2]})


init()
op({"type": "scene.switch", "scene_id": "ship"})
fire(EVENTS[0])
time.sleep(5)
_, ok = op({"type": "clock.hold"})
if not ok:
    sys.exit("the clock wasn't held")
pending = [e for e in EVENTS if e[0] > 0]
n = int(END / 1000 * FPS)
t0 = time.time()
stepped = 0
try:
    for i in range(n):
        t_ms = round(i * 1000 / FPS)
        if t_ms > stepped:
            op({"type": "clock.step", "ms": t_ms - stepped})
            stepped = t_ms
        while pending and pending[0][0] <= t_ms:
            fire(pending.pop(0))
        if not snap(os.path.join(OUT, f"f{i:04d}.png")):
            sys.exit(f"snapshot {i} failed")
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{n}  {(time.time() - t0) / (i + 1):.2f} s a frame", flush=True)
finally:
    op({"type": "clock.release"})
print("done", round(time.time() - t0))
