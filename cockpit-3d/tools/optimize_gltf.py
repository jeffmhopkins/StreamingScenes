"""Takes out of the finished cockpit.gltf what costs render time and shows nothing.

    python optimize_gltf.py <cockpit.gltf> [--keep-throttle-out] [--keep-glass-lit] [--keep-hidden]

Run it last, after finish_gltf.py (and add_live_panels.py). It does three things, each of
which leaves the picture as it was:

- **The throttle lever joins the cockpit**, as a node `throttle` at its hinge. A renderer
  that gives every model its own full-screen layers pays for a second model by the
  screen, not by the triangle, so a 408-triangle lever cost as much as a tenth of the
  cabin. `throttle.gltf` stays beside the model for a scene that wants to move the
  lever: build the cockpit with `--keep-throttle-out` for that scene.
- **The glass becomes unlit.** It is 5% opaque, so 95% of whatever lighting it gets is
  thrown away, and it covers every window. Unlit, it still dims what is behind it by the
  same 5%.
- **Triangles that can never be seen are removed.** A triangle stays if it is the
  nearest surface in any pixel seen from any point a camera can reach inside the cabin
  (a grid through the free space, and every view in ../daw/views.py), or from any
  direction outside (so the hull still casts the same shadows). A triangle too
  small or thin to cover a pixel in a view is judged within a pixel of its outline, so
  it isn't missed. Glass, decals and anything else that hides nothing always stays.
  What goes is faces buried inside the consoles and behind the panels. Afterwards the
  depth picture of every one of those views is compared with the one before: they must
  be identical, or nothing is written.

It needs numpy and a C compiler (`cc`), for visibility.c beside it. It is safe to run
again: the lever isn't added twice, and a second pass finds nothing more to remove.
"""
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CTYPE = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}
COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
TYPE_OF = {v: k for k, v in COMPONENTS.items()}
# The space a camera can be in: the cabin's free air, from near the deck to under the roof.
EYES_X = [-0.72, -0.48, -0.24, 0.0, 0.24, 0.48, 0.72]
EYES_Y = [0.25, 0.55, 0.85, 1.1, 1.3, 1.5, 1.72]
EYES_Z = [-0.58, -0.32, -0.06, 0.2, 0.46, 0.72, 0.98]
CUBE = 1024
OUTSIDE_DIRECTIONS = 300
OUTSIDE = 2048


def read(path):
    """The glTF and its primitives as arrays: [(mesh index, primitive dict, {attribute:
    array}, indices as (n, 3))]."""
    g = json.load(open(path))
    folder = os.path.dirname(path)
    buffers = [open(os.path.join(folder, b["uri"]), "rb").read() for b in g["buffers"]]

    def accessor(i):
        a = g["accessors"][i]
        view = g["bufferViews"][a["bufferView"]]
        n = COMPONENTS[a["type"]]
        dt = np.dtype("<" + CTYPE[a["componentType"]])
        at = view.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = view.get("byteStride", dt.itemsize * n)
        data = buffers[view["buffer"]]
        if stride == dt.itemsize * n:
            return np.frombuffer(data, dt, a["count"] * n, at).reshape(a["count"], n).copy()
        return np.stack([np.frombuffer(data, dt, n, at + k * stride) for k in range(a["count"])])

    prims = []
    for mi, mesh in enumerate(g["meshes"]):
        for p in mesh["primitives"]:
            if p.get("mode", 4) != 4 or "indices" not in p:
                sys.exit(f"{path}: a primitive of mesh {mesh.get('name')} is not indexed triangles")
            attrs = {k: accessor(v) for k, v in p["attributes"].items()}
            prims.append([mi, p, attrs, accessor(p["indices"]).reshape(-1, 3).astype(np.int64)])
    return g, prims


def write(path, g, prims):
    """Writes the glTF with `prims` as its only geometry, in one new buffer."""
    blob = bytearray()
    g["accessors"], g["bufferViews"] = [], []

    def put(array, target):
        while len(blob) % 4:
            blob.append(0)
        g["bufferViews"].append({"buffer": 0, "byteOffset": len(blob),
                                 "byteLength": array.nbytes, "target": target})
        blob.extend(array.tobytes())
        return len(g["bufferViews"]) - 1

    for mesh in g["meshes"]:
        mesh["primitives"] = []
    for mi, p, attrs, idx in prims:
        out = {k: v for k, v in p.items() if k not in ("attributes", "indices")}
        out["attributes"] = {}
        for name, array in attrs.items():
            array = np.ascontiguousarray(array, "<f4")
            acc = {"bufferView": put(array, 34962), "componentType": 5126,
                   "count": len(array), "type": TYPE_OF[array.shape[1]]}
            if name == "POSITION":
                acc["min"] = [float(v) for v in array.min(axis=0)]
                acc["max"] = [float(v) for v in array.max(axis=0)]
            g["accessors"].append(acc)
            out["attributes"][name] = len(g["accessors"]) - 1
        wide = len(attrs["POSITION"]) > 65535
        flat = np.ascontiguousarray(idx.reshape(-1), "<u4" if wide else "<u2")
        g["accessors"].append({"bufferView": put(flat, 34963), "componentType": 5125 if wide else 5123,
                               "count": len(flat), "type": "SCALAR"})
        out["indices"] = len(g["accessors"]) - 1
        g["meshes"][mi]["primitives"].append(out)
    uri = g["buffers"][0]["uri"]
    g["buffers"] = [{"byteLength": len(blob), "uri": uri}]
    with open(os.path.join(os.path.dirname(path), uri), "wb") as f:
        f.write(blob)
    json.dump(g, open(path, "w"), separators=(",", ":"))


def pivot(path):
    """The throttle's hinge in the cockpit's coordinates, from the README's table."""
    readme = os.path.join(os.path.dirname(path), "..", "README.md")
    for line in open(readme, encoding="utf-8"):
        if line.startswith("| Hinge (pivot)"):
            nums = re.findall(r"\(([-−\d.,\s]+)\)", line)[0].replace("−", "-")
            return [float(v) for v in nums.split(",")]
    sys.exit(f"{readme} has no row for the hinge")


def add_throttle(path, g, prims):
    """Adds throttle.gltf's lever at its hinge as the node `throttle`."""
    if any(n.get("name") == "throttle" for n in g["nodes"]):
        return 0
    lever_path = os.path.join(os.path.dirname(path), "throttle.gltf")
    if not os.path.exists(lever_path):
        print("no throttle.gltf beside the model: the lever stays out")
        return 0
    lever, lever_prims = read(lever_path)
    names = {m["name"]: i for i, m in enumerate(g["materials"])}
    at = np.array(pivot(path), "f4")
    g["meshes"].append({"name": "throttle", "primitives": []})
    g["nodes"].append({"mesh": len(g["meshes"]) - 1, "name": "throttle"})
    g["scenes"][g.get("scene", 0)]["nodes"].append(len(g["nodes"]) - 1)
    added = 0
    for _, p, attrs, idx in lever_prims:
        name = lever["materials"][p["material"]]["name"]
        if name not in names:
            sys.exit(f"throttle.gltf uses the material {name}, which the cockpit lacks")
        attrs["POSITION"] = attrs["POSITION"] + at
        prims.append([len(g["meshes"]) - 1, {"material": names[name]}, attrs, idx])
        added += len(idx)
    return added


def unlight_glass(g):
    """Makes every nearly clear blended material unlit."""
    changed = []
    for m in g["materials"]:
        alpha = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])[3]
        if m.get("alphaMode") == "BLEND" and alpha <= 0.1 and "emissiveFactor" not in m:
            if "KHR_materials_unlit" not in m.get("extensions", {}):
                m.setdefault("extensions", {})["KHR_materials_unlit"] = {}
                changed.append(m["name"])
    used = set(g.get("extensionsUsed", []))
    for m in g["materials"]:
        used |= set(m.get("extensions", {}))
    g["extensionsUsed"] = sorted(used)
    return changed


def commands(path, lo, hi):
    """Every view the visibility is judged from, as visibility.c's commands."""
    out = []
    # The show's own views, at twice the canvas, so nothing a view shows is missed.
    os.environ["COCKPIT_MODEL"] = os.path.abspath(path)
    sys.path.insert(0, os.path.join(HERE, "..", "daw"))
    import views
    from shots import CX, CY, MID, S

    def metres(q):
        return ((q["x"] - CX) / S + MID[0], -(q["y"] - CY) / S + MID[1], q["z"] / S + MID[2])

    for shot in views.SHOTS.values():
        eye, target = metres(shot["position"]), metres(shot["target"])
        out.append("P 3840 2160 %f %f %f %f %f %f %f" % (*eye, *target, shot["fov_deg"]))
        out.append("C %d %f %f %f" % (2 * CUBE, *eye))
    for x in EYES_X:
        for y in EYES_Y:
            for z in EYES_Z:
                out.append("C %d %f %f %f" % (CUBE, x, y, z))
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    width = 1.05 * math.sqrt(sum((b - a) ** 2 for a, b in zip(lo, hi)))
    for i in range(OUTSIDE_DIRECTIONS):
        y = 1 - 2 * (i + 0.5) / OUTSIDE_DIRECTIONS
        r = math.sqrt(1 - y * y)
        a = i * math.pi * (3 - math.sqrt(5))
        out.append("O %d %f %f %f %f %f %f %f" % (OUTSIDE, r * math.cos(a), y, r * math.sin(a), *centre, width))
    return out


def see(tool, work, tris, flags, cmds, tag):
    """Runs visibility.c over `cmds` on every core: what each triangle is seen from, and
    each view's depth hash."""
    soup = os.path.join(work, tag + ".bin")
    with open(soup, "wb") as f:
        f.write(struct.pack("<i", len(tris)))
        f.write(np.ascontiguousarray(tris, "<f4").tobytes())
        f.write(np.ascontiguousarray(flags, "<i4").tobytes())
    jobs = os.cpu_count() or 1
    running = []
    for j in range(jobs):
        out = os.path.join(work, f"{tag}{j}.vis")
        proc = subprocess.Popen([tool, soup, out], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        proc.stdin.write("\n".join(cmds[j::jobs]) + "\n")
        proc.stdin.close()
        running.append((proc, out))
    seen = np.zeros(len(tris), np.uint8)
    hashes = []
    for proc, out in running:
        hashes.append(proc.stdout.read())
        if proc.wait() != 0:
            sys.exit("visibility failed")
        seen |= np.fromfile(out, np.uint8)
    return seen, hashes


def remove_hidden(path, g, prims):
    """Removes the triangles nothing can see; returns how many."""
    hides_nothing = [m.get("alphaMode", "OPAQUE") != "OPAQUE" for m in g["materials"]]
    tris = np.concatenate([a["POSITION"][idx].reshape(-1, 9) for _, _, a, idx in prims])
    flags = np.concatenate([np.full(len(idx), int(hides_nothing[p["material"]]), np.int32)
                            for _, p, _, idx in prims])
    points = tris.reshape(-1, 3)
    cmds = commands(path, points.min(axis=0), points.max(axis=0))
    with tempfile.TemporaryDirectory() as work:
        tool = os.path.join(work, "visibility")
        subprocess.run([os.environ.get("CC", "cc"), "-O2", "-o", tool,
                        os.path.join(HERE, "visibility.c"), "-lm"], check=True)
        seen, before = see(tool, work, tris, flags, cmds, "before")
        keep = (seen != 0) | (flags != 0)
        if keep.all():
            return 0
        _, after = see(tool, work, tris[keep], flags[keep], cmds, "after")
        if after != before:
            sys.exit("the depth picture changed in some view: nothing written")
    at = 0
    kept = []
    for mi, p, attrs, idx in prims:
        mine = keep[at:at + len(idx)]
        at += len(idx)
        idx = idx[mine]
        if not len(idx):
            continue
        used = np.unique(idx)
        remap = np.zeros(len(attrs["POSITION"]), np.int64)
        remap[used] = np.arange(len(used))
        kept.append([mi, p, {k: v[used] for k, v in attrs.items()}, remap[idx]])
    prims[:] = kept
    return int((~keep).sum())


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = set(a for a in sys.argv[1:] if a.startswith("--"))
    if len(args) != 1 or flags - {"--keep-throttle-out", "--keep-glass-lit", "--keep-hidden"}:
        sys.exit(__doc__)
    path = args[0]
    g, prims = read(path)
    before = sum(len(idx) for *_, idx in prims)
    if "--keep-throttle-out" not in flags:
        print("throttle lever: added", add_throttle(path, g, prims), "triangles")
    if "--keep-glass-lit" not in flags:
        print("unlit now:", ", ".join(unlight_glass(g)) or "nothing new")
    if "--keep-hidden" not in flags:
        print("never seen: removed", remove_hidden(path, g, prims), "triangles")
    write(path, g, prims)
    print("triangles", before, "to", sum(len(idx) for *_, idx in prims))


if __name__ == "__main__":
    main()
