"""Renders the final cut frame by frame on JStream's held clock, with the camera set by
hand each frame along a straight, eased path between the shots (a true dolly: position
and aim move in straight lines), and the cabin lights dimmed by hand for the warp.

The scene is build_scene.py's, built with PAGES_URL (the 2D cockpit's space and warp
pages outside). The engine plays the warp page's keyframe, the monitors and the feed on
the held clock. Serve the pages slowed to match the frame time (slowserve.py, SLOW about
seconds-a-frame x fps).

    python3 render_final.py <frames dir>
"""
import os
import sys
import time

from mcp import batch, init, op, snap
from shots import SHOTS

OUT = sys.argv[1]
FPS = 30.0
os.makedirs(OUT, exist_ok=True)

# (start s, shot, glide s): into the seat, look up at the overhead screens, settle on
# the windshield for the jump, then dolly in to the centre monitor.
PATH = [(0.0, "cockpit", 0.0), (1.5, "seat", 4.2), (7.0, "window", 3.2),
        (11.5, "warp", 2.4), (20.0, "monitor", 4.2)]
WARP_AT = 12.5
# The lights the warp turns down (build_scene.py's warp variant), and back up for the
# monitor: (light, level in warp). They dim over 11.5-13.9 s and come back over 20-24.2 s.
LIGHTS = [("l_ambient", 0.0), ("l_sun", 0.0), ("l_cabin", 0.0), ("l_rear", 0.0), ("l_glow", 0.4)]
DIM = (11.5, 2.4)
UNDIM = (20.0, 4.2)
END = 26.0


def ease(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def mix(a, b, k):
    c = dict(a)
    for key in ("position", "target"):
        c[key] = {x: a[key][x] + (b[key][x] - a[key][x]) * k for x in "xyz"}
    c["fov_deg"] = a["fov_deg"] + (b["fov_deg"] - a["fov_deg"]) * k
    return c


def camera_at(t):
    cam = SHOTS[PATH[0][1]]
    for start, shot, dur in PATH[1:]:
        if t < start:
            break
        p = 1.0 if dur == 0 else min(1.0, (t - start) / dur)
        cam = mix(cam, SHOTS[shot], ease(p))
    return {k: v for k, v in cam.items() if k not in ("focus_px", "blur_px")}


def dim_at(t):
    """0 with the lights up, 1 in the warp."""
    d = ease(min(1.0, max(0.0, (t - DIM[0]) / DIM[1])))
    u = ease(min(1.0, max(0.0, (t - UNDIM[0]) / UNDIM[1])))
    return d * (1 - u)


init()
op({"type": "scene.set_keyframe", "scene_id": "outside"})
op({"type": "scene.switch", "scene_id": "cockpit"})
time.sleep(3)
op({"type": "clock.hold"})
n = int(END * FPS)
stepped, warped, t0 = 0, False, time.time()
try:
    for i in range(n):
        t = i / FPS
        t_ms = round(t * 1000)
        if t_ms > stepped:
            op({"type": "clock.step", "ms": t_ms - stepped})
            stepped = t_ms
        if not warped and t >= WARP_AT:
            op({"type": "scene.set_keyframe", "scene_id": "outside", "keyframe_id": "outside_warp"})
            warped = True
        k = dim_at(t)
        batch([{"type": "scene.set_camera", "scene_id": "cockpit", "camera": camera_at(t)}]
              + [{"type": "item.set_opacity", "scene_id": "cockpit", "item_id": lid,
                  "opacity": 1.0 + (lvl - 1.0) * k} for lid, lvl in LIGHTS], "frame")
        if not snap(os.path.join(OUT, f"f{i:04d}.png")):
            sys.exit(f"snapshot {i} failed")
        if (i + 1) % 20 == 0:
            print(f"{i + 1}/{n}  {(time.time() - t0) / (i + 1):.2f} s a frame", flush=True)
finally:
    op({"type": "clock.release"})
print("done", round(time.time() - t0))
