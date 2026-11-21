"""Renders the demo frame by frame through `video.snapshot`, for a machine too slow to
record it live.

The shot list is drive.py's. Each frame sets the program camera where the glide would
have it at that moment, with the same per-field ease-in-out a `move` preset applies,
moves the feed's scan bar where its motion would have it, and saves a snapshot. So the
video's timing doesn't depend on how fast the machine composites. Snapshots are at most
1280 px wide, so the frames are 1280 x 720. Frames already on disk are kept, so a stopped
run resumes.

    python3 render_frames.py <frames dir> [fps]
    ffmpeg -framerate 30 -i <frames dir>/f%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p cockpit-demo.mp4
"""
import os
import sys
import time

from mcp import init, op, batch, snap
from shots import SHOTS

if len(sys.argv) < 2:
    sys.exit(__doc__)
OUT = sys.argv[1]
FPS = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
os.makedirs(OUT, exist_ok=True)

# (start s, variant, glide s): drive.py's events, with each preset's duration.
EVENTS = [(0.0, "cockpit", 0.0), (2.5, "seat", 4.2), (9.0, "window", 3.2),
          (15.5, "monitor", 4.2), (23.5, "cockpit", 4.2)]
END = 30.0
FIELDS = ["fov_deg", "focus_px", "blur_px"]


def ease(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def mix(a, b, k):
    c = dict(a)
    for key in ("position", "target"):
        c[key] = {x: a[key][x] + (b[key][x] - a[key][x]) * k for x in "xyz"}
    for f in FIELDS:
        c[f] = a[f] + (b[f] - a[f]) * k
    return c


def camera_at(t):
    cam = SHOTS[EVENTS[0][1]]
    for start, vid, dur in EVENTS[1:]:
        if t < start:
            break
        p = 1.0 if dur == 0 else min(1.0, (t - start) / dur)
        cam = mix(cam, SHOTS[vid], ease(p))
    return cam


def bar_y(t):
    # The feed's triangle oscillation: amplitude 520 around the middle, period 4 s.
    ph = (t / 4.0) % 1.0
    tri = 4 * ph - 1 if ph < 0.5 else 3 - 4 * ph
    return 540 + 520 * tri


init()
op({"type": "scene.switch", "scene_id": "cockpit"})
op({"type": "item.set_motion", "scene_id": "feed", "item_id": "bar", "motion": []})
n = int(END * FPS)
t0 = time.time()
done = 0
for i in range(n):
    path = os.path.join(OUT, f"f{i:04d}.png")
    if os.path.exists(path):
        continue
    t = i / FPS
    batch([
        {"type": "scene.set_camera", "scene_id": "cockpit", "camera": camera_at(t)},
        {"type": "item.set_geometry", "scene_id": "feed", "item_id": "bar",
         "geometry": {"center": {"x": 960, "y": bar_y(t)}, "size": {"width": 1920, "height": 10}}},
    ], "frame")
    if not snap(path + ".tmp"):
        sys.exit(f"snapshot {i} failed")
    os.replace(path + ".tmp", path)
    done += 1
    if done % 20 == 0:
        el = time.time() - t0
        print(f"{i + 1}/{n}  {el / done:.2f} s a frame", flush=True)
print("done", round(time.time() - t0))
