"""The cockpit model's placement in the scene, and the demo's camera shots.

Shared by build_scene.py, which makes the shots keyframe variants, and render_frames.py,
which steps the camera between them.
"""

import json
import os
import re
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
# The model: COCKPIT_MODEL names another copy, such as one from a branch.
MODEL = os.environ.get("COCKPIT_MODEL") or os.path.normpath(
    os.path.join(HERE, "..", "model", "cockpit.gltf"))


def _bounds(path):
    """The model's bounds in metres, from its position accessors (its nodes carry no
    transforms)."""
    g = json.load(open(path))
    lo, hi = [1e9] * 3, [-1e9] * 3
    for mesh in g["meshes"]:
        for prim in mesh["primitives"]:
            a = g["accessors"][prim["attributes"]["POSITION"]]
            lo = [min(x, y) for x, y in zip(lo, a["min"])]
            hi = [max(x, y) for x, y in zip(hi, a["max"])]
    return tuple(lo), tuple(hi)


# The model's bounds (glTF: +y up, +z toward the back of the cabin), and the scale the
# item fits it at: 1000 px a metre, so the item's box is the bounds' size in mm.
BOUNDS_MIN, BOUNDS_MAX = _bounds(MODEL)
S = 1000.0
CX, CY = 960.0, 540.0
MID = [(a + b) / 2 for a, b in zip(BOUNDS_MIN, BOUNDS_MAX)]


def p(x, y, z):
    """A point of the model, in metres, in the scene's space (x right, y down, z toward
    the viewer), with the model's item centred on the canvas at depth 0."""
    return {"x": CX + S * (x - MID[0]), "y": CY - S * (y - MID[1]), "z": S * (z - MID[2])}


def dist(a, b):
    return sum((a[k] - b[k]) ** 2 for k in "xyz") ** 0.5


def camera(eye, look, fov, focus=None, blur=0.0):
    """A scene camera from `eye` to `look` (model metres). `focus` is a point, also in
    model metres, whose distance from the eye becomes the focus distance."""
    e, t = p(*eye), p(*look)
    cam = {"position": e, "target": t, "fov_deg": fov, "roll_deg": 0.0, "depth_sort": True}
    # Depth of field only on request (DOF=1): looking out of a cockpit, everything from
    # the dash to the stars should be sharp.
    if focus is not None and os.environ.get("DOF", "0") == "1":
        f = p(*focus)
        # The focus distance runs along the viewing axis: project eye-to-focus onto it.
        axis = [t[k] - e[k] for k in "xyz"]
        n = sum(c * c for c in axis) ** 0.5
        along = sum((f[k] - e[k]) * axis[i] / n for i, k in enumerate("xyz"))
        cam["focus_px"] = max(along, 1.0)
        cam["blur_px"] = blur
    return cam


# Where the pilot sits and the centre monitor is, read from the model and its README, so
# the shots follow the model as it changes.
def _readme_point(label):
    """The `(x, y, z)` the model's README gives on the table row that starts with `label`."""
    readme = os.path.join(os.path.dirname(MODEL), "..", "README.md")
    for line in open(readme, encoding="utf-8"):
        if line.startswith("| " + label):
            nums = re.findall(r"\(([-\u2212\d.,\s]+)\)", line)[0].replace("\u2212", "-")
            return tuple(float(v) for v in nums.split(","))
    raise SystemExit(f"{readme} has no row for {label}")


def _screen(name):
    """The middle of a screen node and the unit normal it faces, toward +z."""
    g = json.load(open(MODEL))
    node = next(n for n in g["nodes"] if n.get("name") == name)
    prim = g["meshes"][node["mesh"]]["primitives"][0]
    acc = g["accessors"][prim["attributes"]["POSITION"]]
    lo, hi = acc["min"], acc["max"]
    view = g["bufferViews"][acc["bufferView"]]
    data = open(os.path.join(os.path.dirname(MODEL), g["buffers"][view["buffer"]]["uri"]), "rb").read()
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", 12)
    pts = [struct.unpack_from("<3f", data, base + i * stride) for i in range(acc["count"])]
    a = pts[0]
    # The two points farthest apart from the first and from each other span the face.
    b = max(pts, key=lambda q: sum((q[i] - a[i]) ** 2 for i in range(3)))
    c = max(pts, key=lambda q: abs(_cross(_sub(b, a), _sub(q, a))[2]) + abs(_cross(_sub(b, a), _sub(q, a))[1]))
    n = _cross(_sub(b, a), _sub(c, a))
    length = sum(v * v for v in n) ** 0.5
    n = tuple(v / length for v in n)
    if n[2] < 0:
        n = tuple(-v for v in n)
    return tuple((lo[i] + hi[i]) / 2 for i in range(3)), n


def _sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


EYE = _readme_point("Pilot's eye point")
SCREEN, SCREEN_N = _screen("screen_center")
# The back of the cabin, for the establishing shot: 0.25 m in from the rear bulkhead.
BACK = BOUNDS_MAX[2] - 0.25

SHOTS = {
    # From the back of the cabin: the whole pod and the canopy.
    "cockpit": camera((0.42, 1.62, BACK), (0.0, 0.98, SCREEN[2] - 0.1), 66,
                      focus=(0.0, 1.0, (EYE[2] + SCREEN[2]) / 2), blur=6),
    # The pilot's seat, looking at the monitors; the centre one in focus.
    "seat": camera(EYE, (0.0, 1.05, SCREEN[2] - 0.1), 52, focus=SCREEN, blur=12),
    # The same seat, looking up and out: the overhead screens face the pilot's eyes.
    "window": camera(EYE, (0.0, 1.5, -1.0), 58, focus=(0.0, 3.0, -9.0), blur=18),
    # The jump to warp: from the seat, looking out through the windshield at the
    # streaking sky, focused on the canopy frame.
    "warp": camera(EYE, (0.0, 1.32, -3.0), 54, focus=(0.0, 1.3, SCREEN[2] - 0.2), blur=8),
    # Close on the centre monitor, square to it.
    "monitor": camera(
        tuple(SCREEN[i] + 0.62 * SCREEN_N[i] for i in range(3)),
        SCREEN, 44, focus=SCREEN, blur=10),
}

# The throttle lever, a second model with its origin at the hinge.
THROTTLE_PIVOT = _readme_point("Hinge (pivot)")
