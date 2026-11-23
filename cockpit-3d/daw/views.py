"""The DAW cockpit's camera views, in model metres: the cockpit demo's shots
(../jstream/shots.py) and more for the screens it never looked at closely.

render_daw.py glides between them along the song; import_show.py makes each one a
keyframe of the `cockpit` scene, with a hotkey, so a person or an agent switches views
live.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from shots import EYE, SCREEN, SHOTS as _SHOTS, camera  # noqa: E402

DESK = (0.0, 0.69, -0.92)
OVER = (0.0, 1.70, -0.62)
SIDE_L, SIDE_R = (-0.95, 0.86, -0.50), (0.95, 0.86, -0.50)

SHOTS = dict(_SHOTS)
SHOTS["desk"] = camera((0.0, 1.16, -0.52), DESK, 54, focus=DESK, blur=10)
SHOTS["desk_low"] = camera((0.32, 0.98, -0.55), (-0.05, 0.69, -0.95), 50, focus=DESK, blur=12)
SHOTS["overhead"] = camera((0.0, 1.40, -0.14), OVER, 52, focus=OVER, blur=8)
SHOTS["side_l"] = camera((-0.74, 1.12, -0.44), SIDE_L, 42, focus=SIDE_L, blur=10)
SHOTS["side_r"] = camera((0.74, 1.12, -0.44), SIDE_R, 42, focus=SIDE_R, blur=10)
# Out through the windshield at the sky, the canopy only a little soft.
SHOTS["out"] = camera(EYE, (0.0, 1.36, -3.0), 60, focus=(0.0, 1.4, -2.2), blur=4)
SHOTS["seat_wide"] = camera((0.0, 1.30, 0.35), (0.0, 1.0, -1.3), 62, focus=SCREEN, blur=8)

# Focus: sharp everywhere on the wide and seat shots; only the close-ups on one screen
# keep a light depth of field, so the screen reads and the cabin around it softens.
CLOSE = {"desk", "desk_low", "monitor", "monitor_l", "monitor_r", "side_l", "side_r", "overhead"}
for _name, _shot in SHOTS.items():
    if "blur_px" in _shot:
        SHOTS[_name] = dict(_shot, blur_px=3.0 if _name in CLOSE else 0.0)

# The views a person switches between live: (shot, its name in the scene list, the
# hotkey's key after Ctrl+Alt). `cockpit` is the scene's own camera; every other is a
# keyframe of it. The demo's `window` and `warp` shots are left out: `out` covers them.
VIEWS = [
    ("cockpit", "Wide", "Digit1"),
    ("seat_wide", "Behind the seat", "Digit2"),
    ("seat", "Pilot's seat", "Digit3"),
    ("desk", "Desk: clip launcher", "Digit4"),
    ("monitor", "Centre monitor: arrangement", "Digit5"),
    ("monitor_l", "Left monitor: transport", "Digit6"),
    ("monitor_r", "Right monitor: device", "Digit7"),
    ("overhead", "Overhead: mixer and scenes", "Digit8"),
    ("out", "Out the windshield", "Digit9"),
    ("desk_low", "Desk, low", "Digit0"),
    ("side_l", "Left console: clip", "Minus"),
    ("side_r", "Right console: notes", "Equal"),
]
