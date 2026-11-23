"""Glowing screens for the DAW cockpit: a lit card over each picture on the model's
screens, showing that picture's own source, so the screens are brighter than white (the bloom catches
them, the reflection probe sees them bright) and the desk grid's pads glow. The model's
own `screens` material is unlit and can't go past white, so it neither blooms nor reads
as a light source.

`card_at(x0, y0, x1, y1)` returns the geometry (centre, size, and the `rotation_deg`,
`turn_deg` and `tilt_deg` that lay it on the screen) of a card showing that rectangle of
the 1920 x 1080 screens atlas. The corners are the model README's. A card shows a source
of its own, not a crop of the atlas scene: the engine lights a card only when it shows a
source's own frame (observed in its lit-card path, not something an ADR promises), so
only that one glows.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jstream"))
from shots import p  # noqa: E402

# Node: atlas cell (x0, y0, x1, y1), top-left, top-right, bottom-left (metres).
SCREENS = {
    "screen_left": ((0, 0, 640, 360), (-0.796, 1.150, -1.263), (-0.314, 1.116, -1.455), (-0.796, 0.862, -1.212)),
    "screen_center": ((640, 0, 1280, 360), (-0.260, 1.114, -1.465), (0.260, 1.114, -1.465), (-0.260, 0.826, -1.415)),
    "screen_right": ((1280, 0, 1920, 360), (0.314, 1.116, -1.455), (0.796, 1.150, -1.263), (0.314, 0.828, -1.404)),
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


_ANGLES = {}


def _angles(r, d):
    """The tilt, turn and roll whose rotation takes the card's x to `r` and y to `d`."""
    memo = (tuple(np.round(r, 6)), tuple(np.round(d, 6)))
    if memo in _ANGLES:
        return _ANGLES[memo]
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
    _ANGLES[memo] = best
    return best


def card_at(x0, y0, x1, y1, lift_m=0.003):
    """The geometry of a card showing the atlas rectangle (x0, y0) to (x1, y1), laid on
    the screen whose cell holds it, `lift_m` in front of it."""
    for name, (cell, tl, tr, bl) in SCREENS.items():
        cx0, cy0, cx1, cy1 = cell
        if cx0 <= x0 and x1 <= cx1 and cy0 <= y0 and y1 <= cy1:
            break
    else:
        raise ValueError(f"no screen holds {x0, y0, x1, y1}")
    P = {k: np.array([v["x"], v["y"], v["z"]]) for k, v in (("tl", p(*tl)), ("tr", p(*tr)), ("bl", p(*bl)))}
    across, down = P["tr"] - P["tl"], P["bl"] - P["tl"]
    r, d = across / np.linalg.norm(across), down / np.linalg.norm(down)
    n = np.cross(r, d)
    u0, u1 = (x0 - cx0) / (cx1 - cx0), (x1 - cx0) / (cx1 - cx0)
    v0, v1 = (y0 - cy0) / (cy1 - cy0), (y1 - cy0) / (cy1 - cy0)
    centre = P["tl"] + across * (u0 + u1) / 2 + down * (v0 + v1) / 2 + n * lift_m * 1000.0
    _, (tilt, turn, roll) = _angles(r, d)
    return {"center": {"x": float(centre[0]), "y": float(centre[1])},
            "size": {"width": float(np.linalg.norm(across) * (u1 - u0)),
                     "height": float(np.linalg.norm(down) * (v1 - v0))},
            "depth_px": float(centre[2]), "tilt_deg": round(tilt, 3), "turn_deg": round(turn, 3),
            "rotation_deg": round(roll, 3), "fit_mode": "stretch"}


if __name__ == "__main__":
    import json
    print(json.dumps(card_at(0, 720, 600, 1080), indent=1))
