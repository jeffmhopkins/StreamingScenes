"""Adds the console's live panels (live_panels.py) to an exported cockpit.gltf, without
Blender: one node, `live_panels`, of one quad per panel on the `screens` material.

    python tools/add_live_panels.py model/cockpit.gltf

It does nothing to a file that already has the node, which a Blender build of
build_cockpit.py makes itself.
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from live_panels import PANELS, placements, uv  # noqa: E402

B2G = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)  # Blender (x, y, z) -> glTF (x, z, -y)


def main(path):
    g = json.load(open(path))
    if any(n.get("name") == "live_panels" for n in g["nodes"]):
        print("live_panels already there")
        return
    screens = next(i for i, m in enumerate(g["materials"]) if m["name"] == "screens")
    pos, nor, tan, tex, idx = [], [], [], [], []
    for leaf, (top, (w, h), _) in sorted(placements().items()):
        depth = PANELS[leaf][2]
        rot = top[:3, :3]
        u0, v0, u1, v1 = uv(leaf)
        base = len(pos)
        for (lx, lz), (u, v) in zip([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)],
                                    [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]):
            p = top @ np.array([lx, -depth, lz, 1.0])
            pos.append(B2G @ p[:3])
            tex.append((u, 1 - v))
        n = B2G @ (rot @ np.array([0, -1.0, 0]))
        t = B2G @ (rot @ np.array([1.0, 0, 0]))
        nor += [n] * 4
        tan += [(*t, 1.0)] * 4
        idx += [base + 1, base + 3, base, base + 1, base + 2, base + 3]
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

    i_idx = add(idx, 5123, "SCALAR", "<H", 34963)
    i_pos = add([list(map(float, p)) for p in pos], 5126, "VEC3", "<3f", 34962, minmax=True)
    i_nor = add([list(map(float, p)) for p in nor], 5126, "VEC3", "<3f", 34962)
    i_tex = add(tex, 5126, "VEC2", "<2f", 34962)
    i_tan = add([list(map(float, p)) for p in tan], 5126, "VEC4", "<4f", 34962)
    g["meshes"].append({"name": "live_panels", "primitives": [{
        "attributes": {"POSITION": i_pos, "NORMAL": i_nor, "TEXCOORD_0": i_tex, "TANGENT": i_tan},
        "indices": i_idx, "material": screens}]})
    g["nodes"].append({"name": "live_panels", "mesh": len(g["meshes"]) - 1})
    g["scenes"][0]["nodes"].append(len(g["nodes"]) - 1)
    g["buffers"][0]["byteLength"] = len(blob)
    open(binpath, "wb").write(blob)
    with open(path, "w") as f:
        json.dump(g, f, separators=(",", ":"))
    print(f"added {len(PANELS)} live panels")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "model/cockpit.gltf")
