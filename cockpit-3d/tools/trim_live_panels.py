"""Takes the retired readout panels (live_panels.READOUTS_RETIRED) off a cockpit glTF's
`live_panels` node, leaving only the launcher's button panel (live_panels.PANELS), so the
console's amber readouts show their own pictures again.

    python tools/trim_live_panels.py model/cockpit.gltf [more.gltf ...]

It finds each quad by where it is, not by its texture coordinates, so it works on a copy
of the model whose screens were re-mapped (one with a texture per screen). It does
nothing to a file whose `live_panels` holds only the launcher. The bytes of the quads it
drops stay in the .bin, unused (a few hundred bytes).
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from live_panels import PANELS, placements  # noqa: E402

B2G = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)  # Blender (x, y, z) -> glTF (x, z, -y)
NEAR = 0.02  # a kept quad's centre is within 2 cm of its panel's


def keep_centres():
    out = []
    for leaf, (top, _, _) in placements().items():
        if leaf in PANELS:
            p = top @ np.array([0.0, -PANELS[leaf][2], 0.0, 1.0])
            out.append(B2G @ p[:3])
    return out


def read(g, blob, ai, ncomp, fmt):
    a = g["accessors"][ai]
    bv = g["bufferViews"][a["bufferView"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    size = struct.calcsize("<" + fmt)
    stride = bv.get("byteStride", size * ncomp)
    return [struct.unpack_from("<" + fmt * ncomp, blob, off + i * stride) for i in range(a["count"])]


def trim(path):
    g = json.load(open(path))
    node = next((n for n in g["nodes"] if n.get("name") == "live_panels"), None)
    if node is None:
        print(f"{path}: no live_panels node")
        return
    binpath = os.path.join(os.path.dirname(path), g["buffers"][0]["uri"])
    blob = bytearray(open(binpath, "rb").read())
    prim = g["meshes"][node["mesh"]]["primitives"][0]
    pos = np.array(read(g, blob, prim["attributes"]["POSITION"], 3, "f"))
    if "matrix" in node or "translation" in node or "rotation" in node or "scale" in node:
        sys.exit(f"{path}: live_panels has a transform; this tool expects none")
    ia = g["accessors"][prim["indices"]]
    fmt = {5121: "B", 5123: "H", 5125: "I"}[ia["componentType"]]
    idx = [i[0] for i in read(g, blob, prim["indices"], 1, fmt)]
    tris = [idx[i:i + 3] for i in range(0, len(idx), 3)]
    centres = keep_centres()
    # Each quad is its own 4 vertices: group triangles by the quad they share vertices with.
    kept = [t for t in tris
            if min(np.linalg.norm(pos[list(set(t) | _quad_of(t, tris))].mean(0) - c) for c in centres) < NEAR]
    if len(kept) == len(tris):
        print(f"{path}: live_panels already holds only the launcher ({len(tris) // 2} quad)")
        return
    if len(kept) != 2 * len(centres):
        sys.exit(f"{path}: expected {2 * len(centres)} triangles near the launcher, found {len(kept)}")
    flat = [i for t in kept for i in t]
    while len(blob) % 4:
        blob.append(0)
    raw = struct.pack("<" + fmt * len(flat), *flat)
    g["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(raw), "target": 34963})
    blob.extend(raw)
    ia.pop("byteOffset", None)
    ia["bufferView"] = len(g["bufferViews"]) - 1
    ia["count"] = len(flat)
    ia.pop("min", None)
    ia.pop("max", None)
    g["buffers"][0]["byteLength"] = len(blob)
    open(binpath, "wb").write(blob)
    with open(path, "w") as f:
        json.dump(g, f, separators=(",", ":"))
    print(f"{path}: live_panels trimmed from {len(tris) // 2} quads to {len(kept) // 2}")


def _quad_of(t, tris):
    """The vertices of the other triangle sharing an edge with `t` (its quad's other half)."""
    s = set(t)
    for u in tris:
        if u is not t and len(s & set(u)) == 2:
            return set(u)
    return set()


if __name__ == "__main__":
    for p in sys.argv[1:] or ["model/cockpit.gltf"]:
        trim(p)
