"""Renders the DAW cockpit frame by frame on JStream's held clock while sim.py plays the
funk song's Bitwig session into it as JTunnel state, so every frame shows exactly what
the data said at that moment.

Each frame: the simulated session's state for the frame's time goes out as JTunnel
packets (only the keys that changed, and every key once a second as the extension
does), the daemon is given a moment to take them in, the held clock steps one frame,
the camera is set, and the frame is snapshotted. The camera follows the song's
sections; everything else on screen (the launcher, the meters, the screens, the lights,
the sky, the LEDs) is driven by the data inside JStream.

    python3 render_daw.py <session.json> <frames dir> [first last]   # times in seconds

Then mux with the song, which starts after the session's pre-roll (2 s):
    ffmpeg -framerate 30 -i f%04d.png -itsoffset 2 -i funk-song-v42.mp3 ...
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

import sim  # noqa: E402
from mcp import batch, init, op, snap  # noqa: E402
from shots import EYE, SCREEN, SHOTS, camera  # noqa: E402

SESSION, OUT = sys.argv[1:3]
FIRST = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
LAST = float(sys.argv[4]) if len(sys.argv) > 4 else None
FPS = 30.0
SETTLE = float(os.environ.get("SETTLE", "0.12"))  # wall seconds for packets and pages to land
os.makedirs(OUT, exist_ok=True)

# More shots, for the screens the cockpit demo never looked at closely.
DESK = (0.0, 0.69, -0.92)
SHOTS = dict(SHOTS)
SHOTS["desk"] = camera((0.0, 1.16, -0.52), DESK, 54, focus=DESK, blur=10)
SHOTS["desk_low"] = camera((0.32, 0.98, -0.55), (-0.05, 0.69, -0.95), 50, focus=DESK, blur=12)
OVER = (0.0, 1.70, -0.62)
SHOTS["overhead"] = camera((0.0, 1.40, -0.14), OVER, 52, focus=OVER, blur=8)
SIDE_L, SIDE_R = (-0.95, 0.86, -0.50), (0.95, 0.86, -0.50)
SHOTS["side_l"] = camera((-0.74, 1.12, -0.44), SIDE_L, 42, focus=SIDE_L, blur=10)
SHOTS["side_r"] = camera((0.74, 1.12, -0.44), SIDE_R, 42, focus=SIDE_R, blur=10)
# Out through the windshield at the sky, the canopy only a little soft.
SHOTS["out"] = camera(EYE, (0.0, 1.36, -3.0), 60, focus=(0.0, 1.4, -2.2), blur=4)
SHOTS["seat_wide"] = camera((0.0, 1.30, 0.35), (0.0, 1.0, -1.3), 62, focus=SCREEN, blur=8)

# Focus: sharp everywhere on the wide and seat shots; only the close-ups on one screen
# keep a light depth of field, so the screen reads and the cabin around it softens.
CLOSE = {"desk", "desk_low", "monitor", "monitor_l", "monitor_r", "side_l", "side_r", "overhead"}
for name, shot in SHOTS.items():
    if "blur_px" in shot:
        SHOTS[name] = dict(shot, blur_px=3.0 if name in CLOSE else 0.0)

session = sim.Session(SESSION)
PRE = session.pre
B = session.bar
# (session time, shot, glide seconds): the camera follows the arrangement.
PATH = [
    (0.0, "cockpit", 0.0),
    (PRE + 0.0 * B, "seat_wide", 9.0),          # intro: push in as the band starts
    (PRE + 4 * B, "desk", 3.6),                  # verse 1: down to the launcher
    (PRE + 8 * B, "monitor_l", 3.2),             # the transport
    (PRE + 11 * B, "seat", 2.4),                 # into the chorus
    (PRE + 12 * B, "out", 2.0),               # chorus 1: out the window
    (PRE + 16 * B, "monitor", 3.0),              # the arrangement
    (PRE + 20 * B, "overhead", 3.0),             # verse 2: the mixer and the scenes
    (PRE + 24 * B, "monitor_r", 3.0),            # the break: the echo's knobs
    (PRE + 28 * B, "side_r", 3.0),               # the notes
    (PRE + 31 * B, "seat_wide", 2.4),
    (PRE + 32 * B, "cockpit", 2.4),              # chorus 2: wide
    (PRE + 36 * B, "desk_low", 3.6),             # the launcher, low
    (PRE + 40 * B, "side_l", 3.0),               # pre-tag: the clip
    (PRE + 43 * B, "desk", 3.0),                 # the last scene launch
    (PRE + 46 * B, "seat", 2.0),                 # the tag
    (PRE + 49 * B, "cockpit", 5.0),              # pull back
]


def ease(k):
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def mix(a, b, k):
    c = dict(a)
    for key in ("position", "target"):
        c[key] = {x: a[key][x] + (b[key][x] - a[key][x]) * k for x in "xyz"}
    for key in ("fov_deg", "focus_px", "blur_px"):
        if key in a and key in b:
            c[key] = a[key] + (b[key] - a[key]) * k
    return c


def camera_at(t):
    cam = SHOTS[PATH[0][1]]
    for start, shot, dur in PATH[1:]:
        if t < start:
            break
        k = 1.0 if dur == 0 else min(1.0, (t - start) / dur)
        cam = mix(cam, SHOTS[shot], ease(k))
    return cam


init()
tunnel = sim.Tunnel(int(os.environ.get("TUNNEL_PORT", "47251")))
if not tunnel.wait_for_receiver(10):
    sys.exit("no subscribe from JStream: is it running with --jtunnel-accept Bitwig@127.0.0.1:47251?")
end = LAST if LAST is not None else session.end
first = int(FIRST * FPS)
n = int(end * FPS)
# Warm up at the first frame: the pages load, the data arrives, the probe captures.
t = first / FPS
for _ in range(40):
    tunnel.send(session.state(t), everything=True)
    time.sleep(0.05)
op({"type": "scene.set_camera", "scene_id": "cockpit", "camera": camera_at(t)})
time.sleep(2.0)
warm = os.path.join(OUT, "warmup.png")
snap(warm)
os.remove(warm)
op({"type": "clock.hold"})
stepped, t0 = 0, time.time()
try:
    for i in range(first, n):
        t = i / FPS
        # Every key, every frame: a frame takes longer than a second of wall time, and
        # JStream lets a key go stale 3 s (wall time) after it was last sent, as it
        # should for a live sender. A real extension resends each second of its time.
        tunnel.send(session.state(t), everything=True)
        time.sleep(SETTLE)
        t_ms = round((i - first) / FPS * 1000)
        if t_ms > stepped:
            op({"type": "clock.step", "ms": t_ms - stepped})
            stepped = t_ms
        batch([{"type": "scene.set_camera", "scene_id": "cockpit", "camera": camera_at(t)}], "frame")
        if not snap(os.path.join(OUT, f"f{i:04d}.png")):
            sys.exit(f"snapshot {i} failed")
        if (i - first + 1) % 30 == 0:
            print(f"{i + 1}/{n}  {(time.time() - t0) / (i - first + 1):.2f} s a frame", flush=True)
finally:
    op({"type": "clock.release"})
print("done", round(time.time() - t0))
