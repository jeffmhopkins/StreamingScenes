"""The DAW cockpit's camera views, in model metres: the cockpit demo's shots
(../jstream/shots.py) and more for the screens it never looked at closely.

render_daw.py glides between them along the song; import_show.py makes each one a
sequence (`sequences` below), with a hotkey, so a person or an agent switches views live.
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
    ("desk", "Desk: pads", "Digit4"),
    ("monitor", "Centre monitor: arrangement", "Digit5"),
    ("monitor_l", "Left monitor: transport", "Digit6"),
    ("monitor_r", "Right monitor: device", "Digit7"),
    ("overhead", "Overhead: mixer and scenes", "Digit8"),
    ("out", "Out the windshield", "Digit9"),
    ("desk_low", "Desk, low", "Digit0"),
    ("side_l", "Left console: clip", "Minus"),
    ("side_r", "Right console: notes", "Equal"),
]


# ---- the views as sequences (JStream ADR-0183 channels, ADR-0184 sequences) ----
# The cockpit keeps one camera, the wide view's. A channel a camera field (`cam_x`,
# `cam_fov`, ...) offsets it, and each view is a sequence whose lanes glide those channels
# to the view. A lane starts from its channel's value when the sequence starts, so a view
# glides from wherever the camera is: mid-glide, or moved by a Bitwig CC.
RIG = [
    # (channel suffix, its name, the camera property it offsets, the field it reads)
    ("x", "right", "position_x", lambda c: c["position"]["x"]),
    ("y", "down", "position_y", lambda c: c["position"]["y"]),
    ("z", "back", "position_z", lambda c: c["position"]["z"]),
    ("tx", "aim right", "target_x", lambda c: c["target"]["x"]),
    ("ty", "aim down", "target_y", lambda c: c["target"]["y"]),
    ("tz", "aim back", "target_z", lambda c: c["target"]["z"]),
    ("fov", "field of view", "fov", lambda c: c["fov_deg"]),
    ("roll", "roll", "roll", lambda c: c.get("roll_deg", 0.0)),
    ("focus", "focus", "focus", lambda c: c.get("focus_px")),
    ("blur", "blur", "blur", lambda c: c.get("blur_px")),
]
BASE = "cockpit"


def view_id(shot):
    """The view's sequence (a timeline of the `cockpit` scene)."""
    return "view_" + shot


def sequences(glide_ms, smoothing_ms, base=BASE):
    """The views as channels, camera motion and sequences: `(channels, motion, timelines)`.

    Each channel spans what its field does across the views, so it maps 0 to 1 onto the
    least to the most any view adds to the base camera's, and starts at the base view
    (adding nothing). A field no view changes gets no channel. Each sequence is one pass of
    `glide_ms` whose lanes ease every channel from where it is to its view's value.
    """
    cams = {shot: SHOTS[shot] for shot, _, _ in VIEWS}
    b = cams[base]
    channels, motion = [], []
    lanes = {shot: [] for shot in cams}
    for key, label, prop, read in RIG:
        if read(b) is None or any(read(c) is None for c in cams.values()):
            continue
        offset = {shot: read(c) - read(b) for shot, c in cams.items()}
        lo, hi = min(offset.values()), max(offset.values())
        if hi - lo < 1e-3:
            continue
        cid = "cam_" + key
        at = {shot: min(max((o - lo) / (hi - lo), 0.0), 1.0) for shot, o in offset.items()}
        channels.append({"channel_id": cid, "name": "Camera " + label, "default": round(at[base], 6)})
        motion.append({"modifier_id": "view_" + key, "property": prop, "kind": "channel",
                       "channel_id": cid, "smoothing_ms": smoothing_ms,
                       "from": round(lo, 3), "to": round(hi, 3)})
        for shot in cams:
            lanes[shot].append({"target": {"channel": cid},
                                "points": [{"at_ms": glide_ms, "value": round(at[shot], 6),
                                            "curve": "ease_in_out"}]})
    timelines = [{"timeline_id": view_id(shot), "name": "View: " + name,
                  "duration_ms": glide_ms, "lanes": lanes[shot]}
                 for shot, name, _ in VIEWS]
    return channels, motion, timelines
