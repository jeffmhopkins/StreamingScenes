"""The console's live panels: small displays the DAW pages draw, in place of the model's
static readouts and one button panel.

Each entry names a greebled leaf panel of build_cockpit.py, the cell of the `panels`
page view (cockpit-3d/daw/pages/daw.html, PANEL_AT) it shows, and how far in front of the
leaf's face its quad sits. Every quad uses the `screens` material, so it shows the
screens atlas, where build_daw.py puts the `panels` page at PANELS_AT.

build_cockpit.py makes these quads when it builds the model in Blender. add_live_panels.py
adds them to an already exported cockpit.gltf without Blender, from placements() below,
which re-traces build_cockpit.py's greeble() layout (the same seeds and the same order). If
greeble() or the console layout changes, change placements() with it.
"""
import math
import random

import numpy as np

# The `panels` page's place on the 1920 x 1080 screens atlas: the free strip to the right
# of the desk's cell, 320 x 360.
PANELS_AT = (960, 720, 320, 360)

# leaf -> (page cell name, (x, y, w, h) in the page, depth in front of the leaf's face)
READOUT_DEPTH = 0.0072  # just in front of a readout's own quad, at 0.0065
BUTTON_DEPTH = 0.017    # in front of the buttons' faces and their LEDs, at 0.015
PANELS = {
    "console_centrebb": ("launcher", (0, 0, 160, 160), BUTTON_DEPTH),
    "console_wing_L_fwdb": ("status", (160, 0, 160, 80), READOUT_DEPTH),
    "console_centreaab": ("note", (160, 80, 160, 80), READOUT_DEPTH),
    "console_centrebab": ("bend", (0, 160, 160, 80), READOUT_DEPTH),
    "overhead_midbab": ("levels", (160, 160, 160, 80), READOUT_DEPTH),
    "console_wing_R_fwdbbb": ("masterWave", (0, 240, 160, 80), READOUT_DEPTH),
    "overhead_midaa": ("trackWave", (160, 240, 160, 80), READOUT_DEPTH),
    "console_centreaba": ("activity", (0, 320, 80, 40), READOUT_DEPTH),
    "console_wing_L_aftbab": ("position", (80, 320, 80, 40), READOUT_DEPTH),
    "console_wing_R_aftaba": ("beats", (160, 320, 80, 40), READOUT_DEPTH),
    "console_centreaaa": ("strips", (240, 320, 80, 40), READOUT_DEPTH),
}
ATLAS_W, ATLAS_H = 1920, 1080


def uv(leaf):
    """The quad's (u0, v0, u1, v1) on the atlas, v up as Blender has it."""
    _, (x, y, w, h), _ = PANELS[leaf]
    ax, ay = PANELS_AT[0] + x, PANELS_AT[1] + y
    return ax / ATLAS_W, 1 - (ay + h) / ATLAS_H, (ax + w) / ATLAS_W, 1 - ay / ATLAS_H


def button_size(nx, ny, pitch):
    """A live panel over a button grid covers the buttons with a little to spare."""
    return nx * pitch + 0.01, ny * pitch + 0.01


# ---- placements without Blender: a numpy re-trace of build_cockpit.py's greeble() ----

def _t(v):
    m = np.eye(4)
    m[:3, 3] = v
    return m


def _frame(loc, rot):
    a, b, c = (math.radians(t) for t in rot)
    rx = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    ry = np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]])
    rz = np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    m = np.eye(4)
    m[:3, :3] = rz @ ry @ rx
    m[:3, 3] = loc
    return m


def _greeble(name, m, w, h, rnd, out, depth=0):
    if depth < 3 and max(w, h) > 0.16 and (depth < 1 or rnd.random() < 0.8):
        t = rnd.uniform(0.35, 0.65)
        if w >= h:
            wa, wb = w * t, w * (1 - t)
            _greeble(name + "a", m @ _t((-w / 2 + wa / 2, 0, 0)), wa, h, rnd, out, depth + 1)
            _greeble(name + "b", m @ _t((w / 2 - wb / 2, 0, 0)), wb, h, rnd, out, depth + 1)
        else:
            ha, hb = h * t, h * (1 - t)
            _greeble(name + "a", m @ _t((0, 0, -h / 2 + ha / 2)), w, ha, rnd, out, depth + 1)
            _greeble(name + "b", m @ _t((0, 0, h / 2 - hb / 2)), w, hb, rnd, out, depth + 1)
        return
    pw, ph = w - 0.008, h - 0.008
    lift = rnd.choice([0.004, 0.008, 0.012])
    rnd.choice(["paint", "paint_dark", "paint_dark"])
    top = m @ _t((0, -lift, 0))
    kind = rnd.random()
    iw, ih = pw - 0.03, ph - 0.03
    if iw < 0.03 or ih < 0.03:
        return
    size, cell = None, None
    if kind < 0.38:
        rw = min(iw, ih * 2.0)
        cell = rnd.randrange(8 * 16)
        size = (rw, rw / 2)
    elif kind < 0.66:
        pitch = rnd.choice([0.022, 0.026, 0.03])
        nx, ny = max(1, int(iw / pitch)), max(1, int(ih / pitch))
        rnd.randrange(10 ** 6)
        size = button_size(nx, ny, pitch)
    elif kind < 0.78:
        rnd.randrange(10 ** 6)
    if name in PANELS and size:
        out[name] = (top, size, cell)


def placements():
    """leaf -> (its face's 4 x 4 Blender matrix, (w, h) of its live panel, its readout
    atlas cell, or None for buttons)."""
    out = {}
    slope_a, slope_b = (0.65, 0.62), (1.37, 0.79)
    slope_z = lambda y: slope_a[1] + (y - slope_a[0]) * (slope_b[1] - slope_a[1]) / (slope_b[0] - slope_a[0])
    ang = math.degrees(math.atan2(slope_b[1] - slope_a[1], slope_b[0] - slope_a[0]))
    slope = lambda x, y: _frame((x, y, slope_z(y) + 0.002), (-90 + ang, 0, 0))
    rnd = random.Random(12)  # build_console()
    y_c = 1.10
    _greeble("console_centre", slope(0, (y_c + slope_b[0]) / 2 - 0.02), 0.86, 0.2, rnd, out)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        _greeble(f"console_wing_{s}_fwd", slope(side * 0.645, 1.17), 0.36, 0.3, rnd, out)
        _greeble(f"console_wing_{s}_aft", slope(side * 0.645, 0.85), 0.36, 0.3, rnd, out)
    rnd = random.Random(31)  # build_header()
    _greeble("overhead_mid", _frame((0, 0.645, 1.72), (31, 0, 0)), 0.34, 0.2, rnd, out)
    missing = set(PANELS) - set(out)
    if missing:
        raise SystemExit(f"no such readout or button leaf: {sorted(missing)}")
    return out


def draw_placeholders(atlas, readouts):
    """Fills the panels' strip of the screens' placeholder atlas (a PIL image) so the
    model looks as it did before the panels went live: each readout's own cell of the
    readout atlas, and the launcher's buttons as an unlit 8 x 8 pad grid."""
    from PIL import Image, ImageDraw
    cw, ch = readouts.width // 8, readouts.height // 16
    d = ImageDraw.Draw(atlas)
    for leaf, (_, _, cell) in placements().items():
        _, (x, y, w, h), _ = PANELS[leaf]
        x, y = PANELS_AT[0] + x, PANELS_AT[1] + y
        if cell is None:
            d.rectangle([x, y, x + w - 1, y + h - 1], fill=(14, 15, 17))
            p = (w - 6) / 8
            for r in range(8):
                for c in range(8):
                    px, py = x + 4 + c * p, y + 4 + r * p
                    d.rounded_rectangle([px, py, px + p - 4, py + p - 4], 2, fill=(42, 42, 46))
            continue
        c, r = cell % 8, (cell // 8) % 16
        atlas.paste(readouts.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)).resize((w, h), Image.LANCZOS), (x, y))
