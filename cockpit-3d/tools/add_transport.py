"""Adds the transport lights and three seven-segment displays to a cockpit glTF, without
Blender:

- `clock_<name>`: a quad on the `screens` material over an amber readout, one for each
  (live_panels.CLOCKS), mapping a cell of the atlas where the DAW `clocks` page draws
  it: the transport's position and tempo on the left wing in front of the left monitor
  (leaf `console_wing_L_fwdb`), and a stopwatch on the right wing under the right
  monitor (`console_wing_R_fwdbbb`), and the local time up top between the overhead
  monitors (`overhead_midbab`), the last two on raised modules bigger than their readouts;
- `transport_leds`: a row of five LEDs along the readout's far edge, toward the monitor:
  four beat lights, each its own material (`led_beat_1` to `led_beat_4`, amber), and a
  play light, a two-colour LED whose face is stripes of `led_play` (green) and
  `led_stop` (red), so it shows whichever one is lit.

    python tools/add_transport.py model/cockpit.gltf [more.gltf ...]

It adds only what a file lacks: the LEDs (`transport_leds`) and each display
(`clock_<name>`) it doesn't have yet, so a model from the first version, with the
transport's and the stopwatch's displays in one node, `transport_panel`, gains the time. It places by the console's
layout (live_panels.placements), not by texture coordinates, so it also works on a copy
whose screens were re-mapped.
"""
import copy
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from live_panels import ATLAS_W, ATLAS_H, CLOCKS, READOUT_DEPTH, TRANSPORT_LEAF, placements  # noqa: E402

B2G = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)  # Blender (x, y, z) -> glTF (x, z, -y)
LED_W, LED_D, LED_H = 0.010, 0.004, 0.004  # across, deep (toward the monitor), tall
PITCH = 0.016                               # between the beat lights
GAP = 0.010                                 # more before the play light
EDGE = 0.009                                # the row's centre past the readout's far edge
STRIPES = 6                                 # across the play light's face
MODULE_LIFT = 0.012                         # a display module's height off the leaf
MODULE_RIM = 0.006                          # its plastic rim around the display


def materials(g):
    """The new materials' indices, made from the model's own LEDs."""
    names = [m["name"] for m in g["materials"]]

    def like(src, name):
        if name in names:
            return names.index(name)
        m = copy.deepcopy(g["materials"][names.index(src)])
        m["name"] = name
        g["materials"].append(m)
        names.append(name)
        return len(names) - 1
    out = {f"led_beat_{n}": like("led_amber", f"led_beat_{n}") for n in range(1, 5)}
    out["led_play"] = like("led_green", "led_play")
    out["led_stop"] = like("led_red", "led_stop")
    out["plastic"] = names.index("plastic")
    return out


class Mesh:
    def __init__(self):
        self.pos, self.nor, self.tex, self.idx = [], [], [], []

    def quad(self, corners, normal, uvs=((0, 0), (1, 0), (1, 1), (0, 1))):
        b = len(self.pos)
        self.pos += [list(map(float, c)) for c in corners]
        self.nor += [list(map(float, normal))] * 4
        self.tex += [list(map(float, t)) for t in uvs]
        self.idx += [b, b + 1, b + 2, b, b + 2, b + 3]


def to_g(top, lx, ly, lz):
    return B2G @ (top @ np.array([lx, ly, lz, 1.0]))[:3]


def box_sides(mesh, top, cx, cz, w=LED_W, d=LED_D, hgt=LED_H):
    """The four sides of a box w x d, hgt tall, at (cx, cz) on the leaf's face (an LED by
    default)."""
    rot = top[:3, :3]
    x0, x1, z0, z1, y1 = cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2, -hgt
    for (a, b, n) in [((x0, z0), (x1, z0), (0, 0, -1)), ((x1, z0), (x1, z1), (1, 0, 0)),
                      ((x1, z1), (x0, z1), (0, 0, 1)), ((x0, z1), (x0, z0), (-1, 0, 0))]:
        mesh.quad([to_g(top, a[0], 0, a[1]), to_g(top, b[0], 0, b[1]),
                   to_g(top, b[0], y1, b[1]), to_g(top, a[0], y1, a[1])], B2G @ (rot @ np.array(n, float)))


def face(mesh, top, x0, x1, z0, z1, y=-LED_H):
    up = B2G @ (top[:3, :3] @ np.array([0, -1.0, 0]))
    # Counter-clockwise seen from outside (the leaf's -y), or the renderer culls it.
    mesh.quad([to_g(top, x0, y, z0), to_g(top, x1, y, z0), to_g(top, x1, y, z1), to_g(top, x0, y, z1)], up)


def add(path):
    g = json.load(open(path))
    nodes = {n.get("name") for n in g["nodes"]}
    # The displays a file has: a node `clock_<name>` each, or, as the first version made
    # them, the transport's and the stopwatch's in one node, `transport_panel`.
    have = {n[6:] for n in nodes if n and n.startswith("clock_")}
    if "transport_panel" in nodes:
        have |= {"transport", "stopwatch"}
    todo = {leaf: c for leaf, c in CLOCKS.items() if c[0] not in have}
    leds = "transport_leds" not in nodes
    if not leds and not todo:
        print(f"{path}: transport lights and displays already there")
        return
    top, (w, h), _ = placements({TRANSPORT_LEAF: 1})[TRANSPORT_LEAF]
    mats = materials(g)
    meshes = {k: Mesh() for k in mats}  # the LEDs, and `plastic` for the modules
    plastic = mats.pop("plastic")
    cz = h / 2 + EDGE
    x = -w / 2 + LED_W / 2 + 0.004
    for n in range(1, 5):
        m = meshes[f"led_beat_{n}"]
        box_sides(m, top, x, cz)
        face(m, top, x - LED_W / 2, x + LED_W / 2, cz - LED_D / 2, cz + LED_D / 2)
        x += PITCH
    x += GAP - PITCH + LED_W + 0.002
    box_sides(meshes["led_play"], top, x, cz)
    sw = LED_W / STRIPES
    for i in range(STRIPES):
        x0 = x - LED_W / 2 + i * sw
        face(meshes["led_play" if i % 2 == 0 else "led_stop"], top, x0, x0 + sw, cz - LED_D / 2, cz + LED_D / 2)
    # The displays over their readouts, on `screens`, each with its module, if it has one.
    screens = next(i for i, m in enumerate(g["materials"]) if m["name"] == "screens")
    displays = {}
    for leaf, (name, (ax, ay, aw, ah), module) in todo.items():
        panel, box = displays.setdefault(name, (Mesh(), Mesh()))
        t, (pw, ph), _ = placements({leaf: 1})[leaf]
        u0, u1, v0, v1 = ax / ATLAS_W, (ax + aw) / ATLAS_W, ay / ATLAS_H, (ay + ah) / ATLAS_H
        y = -READOUT_DEPTH
        if module:
            # A plastic box over the readout, the display on its top.
            dx, dz, pw, ph = module
            t = t @ np.array([[1, 0, 0, dx], [0, 1, 0, 0], [0, 0, 1, dz], [0, 0, 0, 1.0]])
            bw, bd = pw + 2 * MODULE_RIM, ph + 2 * MODULE_RIM
            box_sides(box, t, 0, 0, bw, bd, MODULE_LIFT)
            face(box, t, -bw / 2, bw / 2, -bd / 2, bd / 2, -MODULE_LIFT)
            y = -MODULE_LIFT - 0.0005
        # glTF v down: the picture's top edge is the readout's +z side (toward the monitor
        # on the console, up on the overhead). Counter-clockwise seen from outside, as add_live_panels.py winds them.
        panel.quad([to_g(t, -pw / 2, y, -ph / 2), to_g(t, pw / 2, y, -ph / 2),
                    to_g(t, pw / 2, y, ph / 2), to_g(t, -pw / 2, y, ph / 2)],
                   B2G @ (t[:3, :3] @ np.array([0, -1.0, 0])), [(u0, v1), (u1, v1), (u1, v0), (u0, v0)])

    binpath = os.path.join(os.path.dirname(path), g["buffers"][0]["uri"])
    blob = bytearray(open(binpath, "rb").read())

    def acc(data, ctype, typ, fmt, target, minmax=False):
        while len(blob) % 4:
            blob.append(0)
        raw = b"".join(struct.pack(fmt, *(row if isinstance(row, (list, tuple)) else [row])) for row in data)
        g["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(raw), "target": target})
        blob.extend(raw)
        a = {"bufferView": len(g["bufferViews"]) - 1, "componentType": ctype, "count": len(data), "type": typ}
        if minmax:
            arr = np.array(data, float)
            a["min"], a["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        g["accessors"].append(a)
        return len(g["accessors"]) - 1

    def prim(mesh, material):
        return {"attributes": {"POSITION": acc(mesh.pos, 5126, "VEC3", "<3f", 34962, True),
                               "NORMAL": acc(mesh.nor, 5126, "VEC3", "<3f", 34962),
                               "TEXCOORD_0": acc(mesh.tex, 5126, "VEC2", "<2f", 34962)},
                "indices": acc(mesh.idx, 5123, "SCALAR", "<H", 34963), "material": material}

    new = [("transport_leds", [prim(meshes[k], mats[k]) for k in mats])] if leds else []
    new += [(f"clock_{name}", [prim(panel, screens)] + ([prim(box, plastic)] if box.idx else []))
            for name, (panel, box) in displays.items()]
    for name, prims in new:
        g["meshes"].append({"name": name, "primitives": prims})
        g["nodes"].append({"name": name, "mesh": len(g["meshes"]) - 1})
        g["scenes"][0]["nodes"].append(len(g["nodes"]) - 1)
    g["buffers"][0]["byteLength"] = len(blob)
    open(binpath, "wb").write(blob)
    with open(path, "w") as f:
        json.dump(g, f, separators=(",", ":"))
    tris = sum(len(p.idx) + len(b.idx) for p, b in displays.values()) // 3
    tris += sum(len(m.idx) for m in meshes.values()) // 3 if leds else 0
    print(f"{path}: added {', '.join(n for n, _ in new)} ({tris} triangles)")


if __name__ == "__main__":
    for p in sys.argv[1:] or ["model/cockpit.gltf"]:
        add(p)
