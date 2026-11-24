"""Makes the cockpit's amber readouts and its small LEDs live: each one shows its own spot of
the screens atlas, which the DAW scene's `readouts` page draws from the session's data.

    python3 tools/live_readouts.py model/cockpit.gltf

The model as build_cockpit.py makes it gives every readout one cell of a fixed picture (the
readout atlas) and every LED one of four glowing materials, so the readouts never change and
the LEDs of a colour can only all do the same thing. This tool, run on the finished model
(after optimize_gltf.py), moves them onto the `screens` material:

- The two side monitors are 22 cm wide, a third of the big ones' 52, yet had a 640 x 360
  cell each. They get 320 x 180 (still more pixels a millimetre than the big monitors),
  side by side in the left half of the old side-left cell. That frees the 640 x 540 below.
- Every readout quad maps a 128 x 64 cell of that space (`READOUT_CELLS`, five a row).
- Every LED of 2 cm or less (the buttons', the toggles', the knobs' and the indicator
  slits') maps a 4 x 4 cell under the readouts, all its corners at the cell's centre, so it
  shows one colour. The larger glowing parts (the monitor light bar, the pillar markers,
  the ledge and desk lights, the overhead lamp) stay on their glowing materials.

It writes the table the page draws from (each readout's look, each LED's colour and place)
into `cockpit-3d/daw/pages/daw.html`, between `@readouts-begin` and `@readouts-end`, and
repaints the placeholder atlas `textures/screens.jpg` so the model looks as it did until a
live source fills those cells. A file it has already changed (no `readout` quads left) is
left alone.
"""
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

ATLAS_W, ATLAS_H = 1920, 1080
# The side monitors' new cells, (x, y, w, h) on the atlas, and the cells they had.
SIDE_AT = {"screen_side_left": (1280, 360, 320, 180), "screen_side_right": (1600, 360, 320, 180)}
SIDE_WAS = {"screen_side_left": (1280, 360, 640, 360), "screen_side_right": (1280, 720, 640, 360)}
# The space the side monitors gave up: the `readouts` page's place on the atlas.
READOUTS_AT = (1280, 540, 640, 540)
READOUT_W, READOUT_H, READOUT_COLS = 128, 64, 5
LED_TOP, LED_CELL = 452, 4          # in the page: the LEDs' rows start under 7 rows of readouts
LED_COLS = READOUTS_AT[2] // LED_CELL
LED_MAX = 0.02                      # an LED at most this long (m) goes live
LED_COLOURS = ["led_amber", "led_red", "led_green", "led_blue"]
# The readout atlas build_cockpit.py maps (make_textures.py draws it): 8 x 16 cells, and
# the look of a cell is (row * 8 + column) % 6.
RO_COLS, RO_ROWS = 8, 16
KINDS = ["digits", "bars", "text", "strips", "wave", "dots"]
PAGE = os.path.join(HERE, "..", "daw", "pages", "daw.html")


def readout_cell(i):
    """Readout i's (x, y) in the page."""
    return (i % READOUT_COLS) * READOUT_W, (i // READOUT_COLS) * READOUT_H


def led_cell(j):
    """LED j's (x, y) in the page."""
    return (j % LED_COLS) * LED_CELL, LED_TOP + (j // LED_COLS) * LED_CELL


class Gltf:
    def __init__(self, path):
        self.path = path
        self.g = json.load(open(path))
        self.binpath = os.path.join(os.path.dirname(path), self.g["buffers"][0]["uri"])
        self.blob = bytearray(open(self.binpath, "rb").read())

    def read(self, i):
        a = self.g["accessors"][i]
        bv = self.g["bufferViews"][a["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        arr = np.frombuffer(self.blob, dt, a["count"] * n, off).copy()
        return arr.reshape(-1, n) if n > 1 else arr

    def add(self, arr, target, minmax=False):
        arr = np.ascontiguousarray(arr)
        if arr.dtype.kind in "iu":
            arr = arr.astype(np.uint32 if arr.max(initial=0) > 65535 else np.uint16)
            ctype = 5125 if arr.dtype == np.uint32 else 5123
        else:
            arr = arr.astype(np.float32)
            ctype = 5126
        while len(self.blob) % 4:
            self.blob.append(0)
        raw = arr.tobytes()
        self.g["bufferViews"].append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": len(raw),
                                      "target": target})
        self.blob.extend(raw)
        typ = "SCALAR" if arr.ndim == 1 else {2: "VEC2", 3: "VEC3", 4: "VEC4"}[arr.shape[1]]
        acc = {"bufferView": len(self.g["bufferViews"]) - 1, "componentType": ctype,
               "count": len(arr), "type": typ}
        if minmax:
            acc["min"], acc["max"] = arr.min(0).tolist(), arr.max(0).tolist()
        self.g["accessors"].append(acc)
        return len(self.g["accessors"]) - 1

    def save(self):
        """Writes the file with only the data something still reads, packed."""
        g, used = self.g, {}
        for m in g["meshes"]:
            for p in m["primitives"]:
                for i in list(p["attributes"].values()) + [p["indices"]]:
                    used[i] = None
        blob, views, accs, remap = bytearray(), [], [], {}
        for i in sorted(used):
            a = dict(g["accessors"][i])
            bv = g["bufferViews"][a["bufferView"]]
            n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
            size = {5126: 4, 5125: 4, 5123: 2}[a["componentType"]] * n * a["count"]
            off = bv.get("byteOffset", 0) + a.pop("byteOffset", 0)
            while len(blob) % 4:
                blob.append(0)
            views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": size, "target": bv["target"]})
            blob.extend(self.blob[off:off + size])
            a["bufferView"] = len(views) - 1
            remap[i] = len(accs)
            accs.append(a)
        for m in g["meshes"]:
            for p in m["primitives"]:
                p["attributes"] = {k: remap[v] for k, v in p["attributes"].items()}
                p["indices"] = remap[p["indices"]]
        g["accessors"], g["bufferViews"] = accs, views
        g["buffers"][0]["byteLength"] = len(blob)
        open(self.binpath, "wb").write(blob)
        with open(self.path, "w") as f:
            json.dump(g, f, separators=(",", ":"))


def parts(pos, idx):
    """Each triangle's connected part: triangles that share a corner's position are one."""
    key = np.round(pos / 1e-4).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    parent = np.arange(inv.max() + 1)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    tris = inv[idx.reshape(-1, 3)]
    for a, b, c in tris:
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    return np.array([find(t[0]) for t in tris])


def facing(pos, nor, tri):
    """`tri` (n x 3 corners) wound so each faces the way its corners' normals point."""
    a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    flip = (np.cross(b - a, c - a) * (nor[tri[:, 0]] + nor[tri[:, 1]] + nor[tri[:, 2]])).sum(1) < 0
    tri = tri.copy()
    tri[flip] = tri[flip][:, [0, 2, 1]]
    return tri


def atlas_uv(x, y):
    return x / ATLAS_W, y / ATLAS_H  # glTF's v runs down from the top, as the atlas's y


def main(path):
    m = Gltf(path)
    g = m.g
    mats = [mt["name"] for mt in g["materials"]]
    screens = mats.index("screens")
    if "readout" not in mats or not any(p["material"] == mats.index("readout")
                                        for me in g["meshes"] for p in me["primitives"]):
        print("no readout quads left: already live")
        return
    readout = mats.index("readout")
    # Where the live panels sit, so a readout under one (live_panels.py) is known.
    live = []
    for nd in g["nodes"]:
        if nd.get("name") == "live_panels":
            for p in g["meshes"][nd["mesh"]]["primitives"]:
                q = m.read(p["attributes"]["POSITION"])
                live += [q[i:i + 4].mean(0) for i in range(0, len(q), 4)]
    readouts, leds = [], []
    for nd in g["nodes"]:
        if "mesh" not in nd:
            continue
        name, mesh = nd["name"], g["meshes"][nd["mesh"]]
        # ---- the side monitors: their quads into their new, smaller cells ----
        if name in SIDE_AT:
            for p in mesh["primitives"]:
                uv = m.read(p["attributes"]["TEXCOORD_0"])
                (ox, oy, ow, oh), (nx, ny, nw, nh) = SIDE_WAS[name], SIDE_AT[name]
                px, py = uv[:, 0] * ATLAS_W, uv[:, 1] * ATLAS_H
                uv[:, 0] = (nx + (px - ox) * nw / ow) / ATLAS_W
                uv[:, 1] = (ny + (py - oy) * nh / oh) / ATLAS_H
                p["attributes"]["TEXCOORD_0"] = m.add(uv, 34962)
            continue
        new = []
        for p in mesh["primitives"]:
            mat = mats[p["material"]]
            if p["material"] == readout:
                pos, nor = m.read(p["attributes"]["POSITION"]), m.read(p["attributes"]["NORMAL"])
                uv, idx = m.read(p["attributes"]["TEXCOORD_0"]), m.read(p["indices"])
                part = parts(pos, idx)
                tri = idx.reshape(-1, 3)
                for k in sorted(set(part), key=lambda k: tri[part == k].min()):
                    vs = np.unique(tri[part == k])
                    u0, v0 = uv[vs].min(0)
                    u1, v1 = uv[vs].max(0)
                    col, row = int((u0 + u1) / 2 * RO_COLS), int((v0 + v1) / 2 * RO_ROWS)
                    i = len(readouts)
                    rx, ry = readout_cell(i)
                    ax, ay = READOUTS_AT[0] + rx, READOUTS_AT[1] + ry
                    # The cell's picture as it was, onto the new cell, the same way up.
                    uv[vs, 0] = (ax + (uv[vs, 0] - u0) / (u1 - u0) * READOUT_W) / ATLAS_W
                    uv[vs, 1] = (ay + (uv[vs, 1] - v0) / (v1 - v0) * READOUT_H) / ATLAS_H
                    centre = pos[vs].mean(0)
                    covered = any(np.linalg.norm(centre - c) < 0.02 for c in live)
                    size = float(np.ptp(pos[vs], axis=0).max())
                    readouts.append({"cell": row * RO_COLS + col, "kind": KINDS[(row * RO_COLS + col) % 6],
                                     "at": [round(float(v), 3) for v in centre], "size": round(size, 3),
                                     "covered": covered, "node": name})
                p["material"] = screens
                p["attributes"]["TEXCOORD_0"] = m.add(uv, 34962)
                p["indices"] = m.add(facing(pos, nor, tri).ravel(), 34963)
            elif mat in LED_COLOURS:
                pos, nor = m.read(p["attributes"]["POSITION"]), m.read(p["attributes"]["NORMAL"])
                uv, idx = m.read(p["attributes"]["TEXCOORD_0"]), m.read(p["indices"])
                tri = idx.reshape(-1, 3)
                part = parts(pos, idx)
                small = np.zeros(len(tri), bool)
                for k in sorted(set(part), key=lambda k: tri[part == k].min()):
                    sel = part == k
                    vs = np.unique(tri[sel])
                    if np.ptp(pos[vs], axis=0).max() > LED_MAX:
                        continue
                    small |= sel
                    j = len(leds)
                    lx, ly = led_cell(j)
                    u, v = atlas_uv(READOUTS_AT[0] + lx + LED_CELL / 2, READOUTS_AT[1] + ly + LED_CELL / 2)
                    uv[vs] = (u, v)
                    leds.append({"colour": LED_COLOURS.index(mat),
                                 "at": [round(float(c), 3) for c in pos[vs].mean(0)], "node": name})
                if not small.any():
                    continue
                if (~small).any():
                    p["indices"] = m.add(tri[~small].ravel(), 34963)
                else:
                    p["drop"] = True
                attrs = dict(p["attributes"], TEXCOORD_0=m.add(uv, 34962))
                new.append({"attributes": attrs, "indices": m.add(facing(pos, nor, tri[small]).ravel(), 34963),
                            "material": screens})
        mesh["primitives"] = [p for p in mesh["primitives"] if not p.get("drop")] + new
    if len(readouts) > READOUT_COLS * (LED_TOP // READOUT_H):
        sys.exit(f"{len(readouts)} readouts don't fit")
    if LED_TOP + (len(leds) + LED_COLS - 1) // LED_COLS * LED_CELL > READOUTS_AT[3]:
        sys.exit(f"{len(leds)} LEDs don't fit")
    m.save()
    write_table(readouts, leds)
    repaint(os.path.join(os.path.dirname(path), "textures"), readouts, leds)
    print(f"{len(readouts)} readouts ({sum(r['covered'] for r in readouts)} under live panels) "
          f"and {len(leds)} LEDs are live")


def write_table(readouts, leds):
    """The page's table: each readout's look and its old cell (the seed of what it shows),
    whether a live panel covers it, and each LED's colour and place (x right, y up, z back, cm)."""
    ro = [[r["cell"], KINDS.index(r["kind"]), int(r["covered"]), int(round(r["size"] * 100))]
          for r in readouts]
    ld = [[l["colour"]] + [int(round(c * 100)) for c in l["at"]] for l in leds]
    block = ("// @readouts-begin: written by cockpit-3d/tools/live_readouts.py; don't edit by hand.\n"
             "// READOUTS: [readout atlas cell, look (KINDS), under a live panel, width in cm]\n"
             "// LEDS: [colour (LED_COLOURS), x, y, z in cm]\n"
             f"const READOUTS = {json.dumps(ro, separators=(',', ':'))};\n"
             f"const LEDS = {json.dumps(ld, separators=(',', ':'))};\n"
             "// @readouts-end")
    html = open(PAGE, encoding="utf-8").read()
    a, b = html.index("// @readouts-begin"), html.index("// @readouts-end") + len("// @readouts-end")
    open(PAGE, "w", encoding="utf-8").write(html[:a] + block + html[b:])


def repaint(textures, readouts, leds):
    """The placeholder atlas: the side monitors' test cards in their new cells, each readout's
    old picture in its cell, and each LED lit in its colour, as the model looked before."""
    from PIL import Image, ImageDraw
    atlas = Image.open(os.path.join(textures, "screens.jpg")).convert("RGB")
    ro = Image.open(os.path.join(textures, "readouts.png")).convert("RGB")
    cards = {n: atlas.crop((x, y, x + w, y + h)) for n, (x, y, w, h) in SIDE_WAS.items()}
    d = ImageDraw.Draw(atlas)
    d.rectangle([1280, 360, 1919, 1079], fill=(0, 0, 0))
    for n, (x, y, w, h) in SIDE_AT.items():
        atlas.paste(cards[n].resize((w, h), Image.LANCZOS), (x, y))
    cw, ch = ro.width // RO_COLS, ro.height // RO_ROWS
    for i, r in enumerate(readouts):
        c, rr = r["cell"] % RO_COLS, r["cell"] // RO_COLS
        x, y = readout_cell(i)
        atlas.paste(ro.crop((c * cw, rr * ch, (c + 1) * cw, (rr + 1) * ch)).resize((READOUT_W, READOUT_H), Image.LANCZOS),
                    (READOUTS_AT[0] + x, READOUTS_AT[1] + y))
    lit = [(255, 140, 13), (255, 20, 13), (38, 255, 89), (38, 140, 255)]
    for j, l in enumerate(leds):
        x, y = led_cell(j)
        x, y = READOUTS_AT[0] + x, READOUTS_AT[1] + y
        d.rectangle([x, y, x + LED_CELL - 1, y + LED_CELL - 1], fill=lit[l["colour"]])
    atlas.save(os.path.join(textures, "screens.jpg"), quality=92, subsampling=0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "model", "cockpit.gltf"))
