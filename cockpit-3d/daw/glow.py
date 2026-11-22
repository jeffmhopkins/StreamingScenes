"""Glowing screens for the DAW cockpit: a lit card over each of the model's screens,
cropped from the same atlas, so the screens are brighter than white (the bloom catches
them, the reflection probe sees them bright) and the desk grid's pads glow. The model's
own `screens` material is unlit and can't go past white, so it neither blooms nor reads
as a light source.

`screen_cards()` returns, per screen, the card's geometry (its centre, size and the
`rotation_deg`, `turn_deg` and `tilt_deg` that lay it on the screen) and its crop of the
1920 x 1080 atlas. The corners are the model README's.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jstream"))
from shots import p  # noqa: E402

# Node: atlas cell (x0, y0, x1, y1), top-left, top-right, bottom-left (metres).
SCREENS = {
    "screen_left": ((0, 0, 640, 360), (-0.811, 1.114, -1.261), (-0.328, 1.114, -1.456), (-0.792, 0.826, -1.214)),
    "screen_center": ((640, 0, 1280, 360), (-0.260, 1.114, -1.465), (0.260, 1.114, -1.465), (-0.260, 0.826, -1.415)),
    "screen_right": ((1280, 0, 1920, 360), (0.328, 1.114, -1.456), (0.811, 1.114, -1.261), (0.309, 0.826, -1.409)),
    "screen_overhead_left": ((0, 360, 640, 720), (-0.530, 1.772, -0.577), (-0.230, 1.772, -0.577), (-0.530, 1.628, -0.663)),
    "screen_overhead_right": ((640, 360, 1280, 720), (0.230, 1.772, -0.577), (0.530, 1.772, -0.577), (0.230, 1.628, -0.663)),
    "screen_side_left": ((1280, 360, 1920, 720), (-1.024, 0.900, -0.406), (-0.967, 0.900, -0.619), (-0.933, 0.820, -0.381)),
    "screen_side_right": ((1280, 720, 1920, 1080), (0.967, 0.900, -0.619), (1.024, 0.900, -0.406), (0.876, 0.820, -0.594)),
    "screen_desk": ((0, 720, 960, 1080), (-0.360, 0.718, -1.052), (0.360, 0.718, -1.052), (-0.360, 0.662, -0.788)),
}


def _rx(a):
    s, c = math.sin(math.radians(a)), math.cos(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    s, c = math.sin(math.radians(a)), math.cos(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    s, c = math.sin(math.radians(a)), math.cos(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _rot(tilt, turn, roll):
    # JStream's ItemGeometry::place: about z, then y, then x.
    return _rx(tilt) @ _ry(turn) @ _rz(roll)


def _angles(r, d):
    """The tilt, turn and roll whose rotation takes the card's x to `r` and y to `d`."""
    want = np.column_stack([r, d, np.cross(r, d)])
    best = None
    for step, span, around in ((10.0, 180.0, (0.0, 0.0, 0.0)), (1.0, 10.0, None), (0.1, 1.0, None),
                               (0.01, 0.1, None)):
        c = around if around is not None else best[1]
        grid = np.arange(-span, span + step / 2, step)
        for a in grid:
            for b in grid:
                for g in grid:
                    ang = (c[0] + a, c[1] + b, c[2] + g)
                    err = np.sum((_rot(*ang) - want) ** 2)
                    if best is None or err < best[0]:
                        best = (err, ang)
        if around is not None:
            pass
    return best


def screen_cards(lift_m=0.003):
    out = {}
    for name, (cell, tl, tr, bl) in SCREENS.items():
        P = {k: np.array([v["x"], v["y"], v["z"]]) for k, v in (("tl", p(*tl)), ("tr", p(*tr)), ("bl", p(*bl)))}
        r, d = P["tr"] - P["tl"], P["bl"] - P["tl"]
        w, h = np.linalg.norm(r), np.linalg.norm(d)
        r, d = r / w, d / h
        n = np.cross(r, d)
        # The card's front faces +z in its own frame; the screen faces the pilot.
        centre = P["tl"] + r * w / 2 + d * h / 2 + n * lift_m * 1000.0
        err, (tilt, turn, roll) = _angles(r, d)
        x0, y0, x1, y1 = cell
        out[name] = {
            "geometry": {"center": {"x": float(centre[0]), "y": float(centre[1])},
                         "size": {"width": float(w), "height": float(h)},
                         "depth_px": float(centre[2]), "tilt_deg": round(tilt, 3),
                         "turn_deg": round(turn, 3), "rotation_deg": round(roll, 3),
                         "fit_mode": "stretch"},
            "crop": {"left": x0, "top": y0, "right": 1920 - x1, "bottom": 1080 - y1},
            "err": float(err),
        }
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(screen_cards(), indent=1))
