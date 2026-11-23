"""Takes out of the finished cockpit.gltf what costs render time and shows nothing.

    python optimize_gltf.py <cockpit.gltf> [--keep-glass-lit] [--keep-hidden]

Run it last, after finish_gltf.py (and add_live_panels.py). It does two things, each of
which leaves the picture as it was:

- **The glass becomes unlit.** It is 5% opaque, so 95% of whatever lighting it gets is
  thrown away, and it covers every window. Unlit, it still dims what is behind it by the
  same 5%.
- **Triangles seen from none of several thousand views are removed.** A triangle stays
  if it is the nearest surface in any pixel of any of them: all six directions from
  each point of a grid through the cabin; from each view in ../daw/views.py and from as
  far around it as the show's camera controls can push it (`REACH`); from points along
  the straight glide between every two views; and from 300 directions outside (so the
  hull still casts the same shadows). A point inside a solid part, where the camera
  would show the backs of surfaces, is left out (`INSIDE`); the views themselves never
  are. A triangle too small or thin to
  cover a pixel in a view is judged within a pixel of its outline, so it isn't missed.
  Glass, decals and anything else that hides nothing always stays. What goes is faces
  buried inside the consoles and behind the panels. Afterwards the depth picture of
  every one of those views is compared with the one before: they must be identical, or
  nothing is written.

  That check is over the same views the choice was made from. A camera somewhere
  between them could still find a sliver of a seam a few pixels wide; the samples are
  dense where the show's cameras go to make that unlikely, not impossible.

Run it on the model as finish_gltf.py left it, not on its own output, when the views or
the reach change: a triangle it has removed is not put back.

It needs numpy and a C compiler (`cc`), for visibility.c beside it, and takes about nine
minutes on four cores. It is safe to run again: a second pass finds nothing more to
remove. It refuses a model with anything it would not write back whole: attributes that
are not floats, morph targets, skins, animations or images kept in the buffer.
"""
import json
import math
import os
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
EYES_Z = [-1.1, -0.84, -0.58, -0.32, -0.06, 0.2, 0.46, 0.72, 0.98]
# How far, in metres, the show's camera controls push the camera from a view: the most
# of ../daw's camera CCs and, where views.py has one, its RIG's reach.
REACH = 0.3
# Where along the glide between two views the camera is sampled.
GLIDE = [0.25, 0.5, 0.75]
# A point where this share or more of what is seen is the back of a surface is inside a
# solid part, not somewhere a camera shows the model from.
INSIDE = 0.25
CUBE = 1024
OUTSIDE_DIRECTIONS = 300
OUTSIDE = 2048


def read(path):
    """The glTF and its primitives as arrays: [(mesh index, primitive dict, {attribute:
    array}, indices as (n, 3))]."""
    g = json.load(open(path))
    for key in ("skins", "animations"):
        if g.get(key):
            sys.exit(f"{path}: has {key}, which this tool would not write back")
    if any("bufferView" in image for image in g.get("images", [])):
        sys.exit(f"{path}: keeps an image in its buffer, which this tool would not write back")
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
            if "targets" in p:
                sys.exit(f"{path}: mesh {mesh.get('name')} has morph targets, which this tool would not write back")
            for name, i in p["attributes"].items():
                a = g["accessors"][i]
                if a["componentType"] != 5126 or a.get("normalized") or "sparse" in a:
                    sys.exit(f"{path}: {name} of mesh {mesh.get('name')} is not plain floats")
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
    # A mesh left with nothing is dropped, with the nodes' references to it.
    kept = [i for i, mesh in enumerate(g["meshes"]) if mesh["primitives"]]
    if len(kept) < len(g["meshes"]):
        new = {old: i for i, old in enumerate(kept)}
        g["meshes"] = [g["meshes"][i] for i in kept]
        for node in g.get("nodes", []):
            if "mesh" in node:
                if node["mesh"] in new:
                    node["mesh"] = new[node["mesh"]]
                else:
                    del node["mesh"]
    uri = g["buffers"][0]["uri"]
    g["buffers"] = [{"byteLength": len(blob), "uri": uri}]
    with open(os.path.join(os.path.dirname(path), uri), "wb") as f:
        f.write(blob)
    json.dump(g, open(path, "w"), separators=(",", ":"))


def unlight_glass(g):
    """Makes every nearly clear blended material unlit."""
    changed = []
    for m in g["materials"]:
        alpha = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])[3]
        if m.get("alphaMode") == "BLEND" and alpha <= 0.1 and "emissiveFactor" not in m:
            if "KHR_materials_unlit" not in m.get("extensions", {}):
                m.setdefault("extensions", {})["KHR_materials_unlit"] = {}
                changed.append(m.get("name", "(unnamed)"))
    used = set(g.get("extensionsUsed", []))
    for m in g["materials"]:
        used |= set(m.get("extensions", {}))
    g["extensionsUsed"] = sorted(used)
    return changed


def commands(path, lo, hi):
    """Every view the visibility is judged from: `(always, points, outside)`, the views'
    own commands, the points a camera might also be at (see `in_free_air`), and the
    commands from outside."""
    out, points = [], []
    # The show's own views, at twice the canvas, so nothing a view shows is missed.
    os.environ["COCKPIT_MODEL"] = os.path.abspath(path)
    sys.path.insert(0, os.path.join(HERE, "..", "daw"))
    import views
    from shots import CX, CY, MID, S

    def metres(q):
        return ((q["x"] - CX) / S + MID[0], -(q["y"] - CY) / S + MID[1], q["z"] / S + MID[2])

    reach = REACH
    for _, _, _, _, how, _ in getattr(views, "RIG", [])[:3]:
        if how[0] == "pad":
            reach = max(reach, how[1] / S)
    eyes = []
    for shot in views.SHOTS.values():
        eye, target = metres(shot["position"]), metres(shot["target"])
        eyes.append(eye)
        out.append("P 3840 2160 %f %f %f %f %f %f %f" % (*eye, *target, shot["fov_deg"]))
        out.append("C %d %f %f %f" % (2 * CUBE, *eye))
        # Around the view, as far as the camera controls push it: the corners of that
        # box and the middles of its faces. Every direction, so any aim, field of view
        # and roll is covered.
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if abs(dx) + abs(dy) + abs(dz) in (1, 3):
                        points.append((eye[0] + dx * reach, eye[1] + dy * reach, eye[2] + dz * reach))
    for i, a in enumerate(eyes):
        for b in eyes[i + 1:]:
            for t in GLIDE:
                points.append(tuple(p + (q - p) * t for p, q in zip(a, b)))
    for x in EYES_X:
        for y in EYES_Y:
            for z in EYES_Z:
                points.append((x, y, z))
    outside = []
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    width = 1.05 * math.sqrt(sum((b - a) ** 2 for a, b in zip(lo, hi)))
    for i in range(OUTSIDE_DIRECTIONS):
        y = 1 - 2 * (i + 0.5) / OUTSIDE_DIRECTIONS
        r = math.sqrt(1 - y * y)
        a = i * math.pi * (3 - math.sqrt(5))
        outside.append("O %d %f %f %f %f %f %f %f" % (OUTSIDE, r * math.cos(a), y, r * math.sin(a), *centre, width))
    return out, points, outside


def soup(work, tag, tris, flags):
    """Writes the triangles as visibility.c reads them; returns the file."""
    path = os.path.join(work, tag + ".bin")
    with open(path, "wb") as f:
        f.write(struct.pack("<i", len(tris)))
        f.write(np.ascontiguousarray(tris, "<f4").tobytes())
        f.write(np.ascontiguousarray(flags, "<i4").tobytes())
    return path


def in_free_air(tool, work, tris, flags, points):
    """The points a camera could show the model from: those not inside a solid part,
    where most of what is seen is the back of a surface and the picture is broken with or
    without the hidden triangles (a control pushed the camera into the roof or a console)."""
    path = soup(work, "air", tris, flags)
    jobs = os.cpu_count() or 1
    running = []
    for j in range(jobs):
        mine = points[j::jobs]
        proc = subprocess.Popen([tool, path, os.devnull], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        proc.stdin.write("".join("B 128 %f %f %f\n" % p for p in mine))
        proc.stdin.close()
        running.append((proc, mine))
    free = set()
    for proc, mine in running:
        shares = [float(line.split()[1]) for line in proc.stdout.read().splitlines()]
        if proc.wait() != 0 or len(shares) != len(mine):
            sys.exit("visibility failed")
        free |= {p for p, share in zip(mine, shares) if share < INSIDE}
    return [p for p in points if p in free]


def see(tool, work, tris, flags, cmds, tag):
    """Runs visibility.c over `cmds` on every core: what each triangle is seen from, and
    each view's depth hash."""
    path = soup(work, tag, tris, flags)
    jobs = os.cpu_count() or 1
    running = []
    for j in range(jobs):
        out = os.path.join(work, f"{tag}{j}.vis")
        proc = subprocess.Popen([tool, path, out], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
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
    flags = np.concatenate([np.full(len(idx), int("material" not in p or hides_nothing[p["material"]]), np.int32)
                            for _, p, _, idx in prims])
    points = tris.reshape(-1, 3)
    cmds, eyes, outside = commands(path, points.min(axis=0), points.max(axis=0))
    with tempfile.TemporaryDirectory() as work:
        tool = os.path.join(work, "visibility")
        subprocess.run([os.environ.get("CC", "cc"), "-O2", "-o", tool,
                        os.path.join(HERE, "visibility.c"), "-lm"], check=True)
        free = in_free_air(tool, work, tris, flags, eyes)
        print("judged from", len(cmds) // 2, "views,", len(free), "of", len(eyes),
              "more points in free air, and", len(outside), "directions outside")
        cmds = cmds + ["C %d %f %f %f" % (CUBE, *p) for p in free] + outside
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
    if len(args) != 1 or flags - {"--keep-glass-lit", "--keep-hidden"}:
        sys.exit(__doc__)
    path = args[0]
    g, prims = read(path)
    before = sum(len(idx) for *_, idx in prims)
    if "--keep-glass-lit" not in flags:
        print("unlit now:", ", ".join(unlight_glass(g)) or "nothing new")
    if "--keep-hidden" not in flags:
        print("never seen: removed", remove_hidden(path, g, prims), "triangles")
    write(path, g, prims)
    print("triangles", before, "to", sum(len(idx) for *_, idx in prims))


if __name__ == "__main__":
    main()
