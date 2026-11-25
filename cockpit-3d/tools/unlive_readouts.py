"""Undoes live_readouts.py's readouts and LEDs on a model it has changed, and keeps its
smaller side-monitor cells: every readout goes back to the `readout` material and its old
readout-atlas cell, and every small LED back to its glowing material, so they light as
build_cockpit.py made them, driven by the scene's material drives.

    python3 tools/unlive_readouts.py model/cockpit.gltf

It reads which cell each readout had and each LED's colour from the table live_readouts.py
wrote into daw/pages/daw.html.
"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_readouts import (ATLAS_H, ATLAS_W, LED_CELL, LED_COLOURS, LED_COLS, LED_TOP,  # noqa: E402
                           PAGE, READOUT_COLS, READOUT_H, READOUT_W, READOUTS_AT, RO_COLS, RO_ROWS, Gltf)


def main(path):
    html = open(PAGE, encoding="utf-8").read()
    ro = json.loads(re.search(r"const READOUTS = (\[.*?\]);\n", html).group(1))
    leds = json.loads(re.search(r"const LEDS = (\[.*?\]);\n", html).group(1))
    m = Gltf(path)
    g = m.g
    mats = [mt["name"] for mt in g["materials"]]
    screens = mats.index("screens")
    rx0, ry0 = READOUTS_AT[:2]
    n_ro = n_led = 0
    for nd in g["nodes"]:
        # Only the parts live_readouts.py changed; other parts on `screens` stay.
        if "mesh" not in nd or nd["name"] not in ("conduits", "dashboard", "header", "side_consoles"):
            continue
        for p in g["meshes"][nd["mesh"]]["primitives"]:
            if p["material"] != screens:
                continue
            uv = m.read(p["attributes"]["TEXCOORD_0"])
            idx = np.unique(m.read(p["indices"]))
            px, py = uv[idx, 0] * ATLAS_W - rx0, uv[idx, 1] * ATLAS_H - ry0
            if py.min() >= LED_TOP:  # an LED primitive: one colour, its first LED's
                j = int(px[0] // LED_CELL) + int((py[0] - LED_TOP) // LED_CELL) * LED_COLS
                p["material"] = mats.index(LED_COLOURS[leds[j][0]])
                n_led += len(set(zip((px // LED_CELL).astype(int), (py // LED_CELL).astype(int))))
                continue
            # A readout primitive: each quad's corners back to its old cell, the cell found
            # from each triangle's centre (a corner sits on its cell's edge).
            tri = m.read(p["indices"]).reshape(-1, 3)
            new = uv.copy()
            for t in tri:
                cx = uv[t, 0].mean() * ATLAS_W - rx0
                cy = uv[t, 1].mean() * ATLAS_H - ry0
                col, row = int(cx // READOUT_W), int(cy // READOUT_H)
                cell = ro[col + row * READOUT_COLS][0]
                for v in t:
                    fx = (uv[v, 0] * ATLAS_W - rx0 - col * READOUT_W) / READOUT_W
                    fy = (uv[v, 1] * ATLAS_H - ry0 - row * READOUT_H) / READOUT_H
                    new[v] = (((cell % RO_COLS) + fx) / RO_COLS, ((cell // RO_COLS) + fy) / RO_ROWS)
            uv = new
            p["material"] = mats.index("readout")
            p["attributes"]["TEXCOORD_0"] = m.add(uv, 34962)
            n_ro += 1
    m.save()
    print(f"{n_ro} readout primitives and {n_led} LED cells back on their own materials")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "model", "cockpit.gltf"))
