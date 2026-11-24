"""The soft keys that light to show what a screen shows: where they are, and which pixels of
the screens atlas light each one.

Each of the three main monitors has a row of five soft keys under it (build_cockpit.py's
screen(): `<screen>_key0` to `_key4`). The hologram gets a row of five of its own, on a
the blank panel on the dash just in front of and right of its projector's lens. A quad on the `screens`
material sits on each key's face, and every corner of it maps the same point of the
atlas, so the whole face is the colour of that one atlas pixel: the DAW scene lights a key
by drawing its pixel bright (cockpit-3d/daw/sources.py).

The pixels are in KEY_STRIP, the bottom 16 px of the readouts' space (live_readouts.py's
READOUTS_AT), under the LEDs' rows, which the readouts page leaves empty
(add_softkeys.py also stops `screen_side_right`'s texture coordinates above the strip,
which its own cell, SIDE_AT, never reaches). Key n of the list KEYS is the 32 x 16 px block n of the strip,
from its left.

Positions are in glTF metres (+y up, the pilot faces -z).
"""
import numpy as np

# The main monitors' corners (the model's README): top-left, top-right, bottom-left.
MONITORS = {
    "screen_left": ((-0.817, 1.118, -1.273), (-0.315, 1.118, -1.407), (-0.817, 0.826, -1.273)),
    "screen_center": ((-0.260, 1.118, -1.415), (0.260, 1.118, -1.415), (-0.260, 0.826, -1.415)),
    "screen_right": ((0.315, 1.118, -1.407), (0.817, 1.118, -1.273), (0.315, 0.826, -1.407)),
}
# build_cockpit.py: the monitors' surround face stands MONITOR_FACE in front of the
# screens, and the side monitors' frames SIDE_RECESS further; each key is a box
# (width * 0.12, 0.012 deep, 0.016 high) centred 2 mm in front of that face, its centre
# (i - 2) * width * 0.19 across and 16 mm under the screen's bottom edge.
MONITOR_FACE, SIDE_RECESS = -0.008, 0.03
KEY_DEPTH, KEY_HIGH = 0.012, 0.016
KEY_BEVEL = 0.003  # the keys' bevel: the quad covers the flat of the face inside it
LIFT = 0.0006      # how far a quad stands off the face it covers

# The atlas strip the keys' pixels are in: x, y, w, h on the 1920 x 1080 atlas.
ATLAS_W, ATLAS_H = 1920, 1080
KEY_STRIP = (1280, 1064, 640, 16)
SLOT_W = 32

# The hologram's keys, on the sloped console just in front of and right of the lens
# (hologram.py's LENS_AT, (0, 0.79, -1.28)), on the blank greeble panel there, whose top
# stands HOLO_PANEL_TOP over the slope.
SLOPE = ((0.65, 0.62), (1.37, 0.79))  # build_cockpit.py's slope, (Blender y, z)
HOLO_KEYS_X, HOLO_KEYS_Z = 0.05, -1.171  # the row's middle, glTF x and z
HOLO_PANEL_TOP = 0.005
HOLO_KEY_W, HOLO_KEY_D, HOLO_KEY_H, HOLO_PITCH = 0.016, 0.011, 0.007, 0.022


def _monitor_keys(name):
    tl, tr, bl = (np.array(v, float) for v in MONITORS[name])
    across, down = tr - tl, bl - tl
    w, h = np.linalg.norm(across), np.linalg.norm(down)
    r, d = across / w, down / h
    n = np.cross(d, r)
    n = n if n[2] > 0 else -n  # toward the pilot
    face = MONITOR_FACE - (0.0 if name == "screen_center" else SIDE_RECESS)
    out = -(face - 0.002 - KEY_DEPTH / 2)  # the key's front face, in front of the screen
    centre = tl + across / 2 + down / 2
    keys = []
    for i in range(5):
        c = centre + r * (i - 2) * w * 0.19 + d * (h / 2 + 0.016) + n * (out + LIFT)
        keys.append((c, r, -d, n, (w * 0.12 - 2 * KEY_BEVEL, KEY_HIGH - 2 * KEY_BEVEL)))
    return keys


def slope_frame():
    """The slope's axes in glTF: across (x), up the slope toward the windshield, and its
    normal (up and toward the pilot)."""
    (y0, z0), (y1, z1) = SLOPE
    along = np.array([0.0, z1 - z0, -(y1 - y0)])
    along /= np.linalg.norm(along)
    n = np.cross(np.array([1.0, 0, 0]), along)
    n = n if n[1] > 0 else -n
    return np.array([1.0, 0, 0]), along, n


def slope_point(x, z):
    """The slope's surface at glTF x, z."""
    (y0, z0), (y1, z1) = SLOPE
    yb = -z
    return np.array([x, z0 + (yb - y0) * (z1 - z0) / (y1 - y0), z])


def holo_keys():
    """The hologram's keys: (name, centre, x axis, y axis (up the slope), normal, size
    (across, along, thick)), sunk 1 mm into the panel they stand on."""
    r, a, n = slope_frame()
    top = slope_point(HOLO_KEYS_X, HOLO_KEYS_Z) + n * (HOLO_PANEL_TOP - 0.001)
    out = []
    for i in range(5):
        c = top + r * (i - 2) * HOLO_PITCH + n * HOLO_KEY_H / 2
        out.append((f"holo_key{i}", c, r, a, n, (HOLO_KEY_W, HOLO_KEY_D, HOLO_KEY_H)))
    return out


def _holo_keys():
    keys = []
    for name, c, r, a, n, (w, d, t) in holo_keys():
        keys.append((c + n * (t / 2 + LIFT), r, a, n, (w - 2 * 0.0015, d - 2 * 0.0015)))
    return keys


# Every lit key, in strip order: (screen, index 0 to 4) -> its quad.
SCREENS = ("screen_left", "screen_center", "screen_right", "hologram")


def keys():
    """[(screen, i, centre, x axis, y axis, normal, (w, h))] for every key, in KEYS order."""
    out = []
    for s in SCREENS:
        row = _holo_keys() if s == "hologram" else _monitor_keys(s)
        out += [(s, i, *k) for i, k in enumerate(row)]
    return out


def slot(n):
    """Key n's block of the atlas: (x, y, w, h)."""
    x, y, _, h = KEY_STRIP
    return x + n * SLOT_W, y, SLOT_W, h


def uv(n):
    """The one point of the atlas key n's quad maps, as glTF (u, v) with v down."""
    x, y, w, h = slot(n)
    return (x + w / 2) / ATLAS_W, (y + h / 2) / ATLAS_H
