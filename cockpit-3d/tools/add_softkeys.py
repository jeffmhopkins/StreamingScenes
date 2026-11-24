"""Gives the cockpit's soft keys lights a scene can drive (softkeys.py), without Blender:

- one node, `softkey_lights`, of a quad on the `screens` material over the face of each of
  the five soft keys under the three main monitors and of the hologram's five keys, each
  mapping one point of the atlas's key strip, so the scene lights a key by its pixel;
- one node, `holo_keys`, the hologram's keys themselves: five keys in `plastic` on the blank
  panel on the dash in front of and right of the projector's lens;
- `screen_side_right`'s texture coordinates trimmed to stop above the key strip (the
  bottom 16 px of the readouts' space), so that screen never shows the keys' pixels (a
  no-op once live_readouts.py has moved it to its own cell above).

    python tools/add_softkeys.py model/cockpit.gltf

It does nothing to a file that already has `softkey_lights`. Run it after
finish_gltf.py (and add_live_panels.py); it can run before or after optimize_gltf.py.
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import softkeys  # noqa: E402


def _quad(c, x, y, n, w, h):
    """Four corners of a w x h quad centred on c in the plane of x and y, facing n,
    counter-clockwise seen from n."""
    hw, hh = x * w / 2, y * h / 2
    pts = [c - hw - hh, c + hw - hh, c + hw + hh, c - hw + hh]
    if np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), n) < 0:
        pts = pts[::-1]
    return pts


def _box(c, x, y, n, size):
    """A box's six faces as quads: (corners, normal, u axis)."""
    w, d, t = size
    faces = []
    for axis, half, (ua, ub, la, lb) in ((n, t / 2, (x, y, w, d)), (-n, t / 2, (x, y, w, d)),
                                         (x, w / 2, (y, n, d, t)), (-x, w / 2, (y, n, d, t)),
                                         (y, d / 2, (x, n, w, t)), (-y, d / 2, (x, n, w, t))):
        faces.append((_quad(c + axis * half, ua, ub, axis, la, lb), axis, ua))
    return faces


class Mesh:
    def __init__(self):
        self.pos, self.nor, self.tan, self.tex, self.idx = [], [], [], [], []

    def quad(self, pts, n, t, uvs):
        base = len(self.pos)
        self.pos += [list(map(float, p)) for p in pts]
        self.nor += [list(map(float, n))] * 4
        self.tan += [[*map(float, t), 1.0]] * 4
        self.tex += [list(map(float, u)) for u in uvs]
        self.idx += [base, base + 1, base + 2, base, base + 2, base + 3]


def main(path):
    g = json.load(open(path))
    if any(nd.get("name") == "softkey_lights" for nd in g["nodes"]):
        print("softkey_lights already there")
        return
    mats = {m["name"]: i for i, m in enumerate(g["materials"])}
    binpath = os.path.join(os.path.dirname(path), g["buffers"][0]["uri"])
    blob = bytearray(open(binpath, "rb").read())

    def add(data, ctype, typ, fmt, target, minmax=False):
        while len(blob) % 4:
            blob.append(0)
        raw = b"".join(struct.pack(fmt, *(row if np.ndim(row) else [row])) for row in data)
        g["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(raw),
                                 "target": target})
        blob.extend(raw)
        acc = {"bufferView": len(g["bufferViews"]) - 1, "componentType": ctype, "count": len(data),
               "type": typ}
        if minmax:
            a = np.array(data, float)
            acc["min"], acc["max"] = a.min(0).tolist(), a.max(0).tolist()
        g["accessors"].append(acc)
        return len(g["accessors"]) - 1

    def node(name, m, material):
        prim = {"attributes": {"POSITION": add(m.pos, 5126, "VEC3", "<3f", 34962, minmax=True),
                               "NORMAL": add(m.nor, 5126, "VEC3", "<3f", 34962),
                               "TEXCOORD_0": add(m.tex, 5126, "VEC2", "<2f", 34962),
                               "TANGENT": add(m.tan, 5126, "VEC4", "<4f", 34962)},
                "indices": add(m.idx, 5123, "SCALAR", "<H", 34963), "material": material}
        g["meshes"].append({"name": name, "primitives": [prim]})
        g["nodes"].append({"name": name, "mesh": len(g["meshes"]) - 1})
        g["scenes"][0]["nodes"].append(len(g["nodes"]) - 1)

    # The hologram's keys, in plastic, its texture laid on at a metre a unit.
    hk = Mesh()
    for _, c, x, y, n, size in softkeys.holo_keys():
        for pts, fn, ua in _box(c, x, y, n, size):
            vb = np.cross(fn, ua)
            hk.quad(pts, fn, ua, [(np.dot(p, ua), np.dot(p, vb)) for p in pts])
    node("holo_keys", hk, mats["plastic"])

    # A lit face on every key, each corner on its one atlas point.
    lit = Mesh()
    for k, (_, _, c, x, y, n, (w, h)) in enumerate(softkeys.keys()):
        lit.quad(_quad(c, x, y, n, w, h), n, x, [softkeys.uv(k)] * 4)
    node("softkey_lights", lit, mats["screens"])

    # The right side screen stops above the key strip.
    side = next(nd for nd in g["nodes"] if nd.get("name") == "screen_side_right")
    acc = g["accessors"][g["meshes"][side["mesh"]]["primitives"][0]["attributes"]["TEXCOORD_0"]]
    bv = g["bufferViews"][acc["bufferView"]]
    off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 8)
    bottom = softkeys.KEY_STRIP[1] / softkeys.ATLAS_H
    for i in range(acc["count"]):
        u, v = struct.unpack_from("<2f", blob, off + i * stride)
        if v > bottom:
            struct.pack_into("<2f", blob, off + i * stride, u, bottom)

    g["buffers"][0]["byteLength"] = len(blob)
    open(binpath, "wb").write(blob)
    with open(path, "w") as f:
        json.dump(g, f, separators=(",", ":"))
    print(f"added {len(softkeys.keys())} key lights and the hologram's keys")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "model/cockpit.gltf")
