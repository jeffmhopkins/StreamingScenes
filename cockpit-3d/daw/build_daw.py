"""Builds the DAW cockpit in a running JStream daemon over MCP: the 3D cockpit, with every
screen and many of its lights following a Bitwig session that arrives as JTunnel state
(sim.py sends it; the daemon runs with `--jtunnel-accept Bitwig@127.0.0.1:47251`).

- The desk's pad surface is JStream's own `grid` source kind: the clip launcher (each
  track a column, each scene a row, from the `track/N` keys' `slots`, blinking while a
  clip is queued), and beside it the tracks' and the master's meters as `bars`.
- The other seven screens are browser pages (pages/daw.html) that read the session's
  live data through the page API: transport, arrangement, device, mixer, scenes, clip
  and notes.
- Lights follow the data through `data` motion modifiers: a light a track over its meter,
  the screens' glow on the beat, the cabin lights up while the transport plays and down
  through the break, and the sky brighter while a chorus clip plays. The model's own
  LEDs and light strips follow the tracks and the beat by material name.
- Each screen has a glowing lit card over it, so the screens and the desk grid bloom and
  show bright in the reflections, and a small light per launcher column throws its
  track's colour on the desk.
- Reflection probes make the cabin's surfaces reflect the screens and lights.

    python3 build_daw.py

The screens' pages are given to JStream inline (`html`), so nothing needs to serve them
and the collection holds them. PAGES=http://127.0.0.1:8765 loads them from a server of
this folder's pages/ instead (serve_pages.py), to try an edited page without building
again. JS_TOKEN and JS_MCP are as for ../jstream/mcp.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from mcp import asset, batch, init, op  # noqa: E402
from shots import BACK, BOUNDS_MAX, BOUNDS_MIN, CX, CY, MODEL, S, SHOTS, p  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from live_panels import PANELS_AT  # noqa: E402

PAGES = os.environ.get("PAGES", "")
DAW_HTML = open(os.path.join(HERE, "pages", "daw.html"), encoding="utf-8").read()
INPUT = os.environ.get("DAW_INPUT", "Bitwig")
PROBE = os.environ.get("PROBE", "1") == "1"
PROBE_EVERY = int(os.environ.get("PROBE_EVERY", "10"))
GLOW = os.environ.get("GLOW", "1") == "1"
# The desk's 8 x 8 pads: `notes` (the default) plays the selected track as an isomorphic
# note grid, rows a fourth apart, from the page's `iso` view; `clips` is the clip launcher.
DESK_GRID = os.environ.get("DESK_GRID", "notes")
# The ship (see the l_env lights below): its heading at rest in degrees, its warp at rest
# (0 to 1), and the MIDI CCs that drive them.
SHIP_YAW = float(os.environ.get("SHIP_YAW", "0"))
WARP = float(os.environ.get("WARP", "0"))
SHIP_CC_CHANNEL = int(os.environ.get("SHIP_CC_CHANNEL", "16"))
SHIP_CC_INPUT = os.environ.get("SHIP_CC_INPUT", "Bitwig")
SHIP_CC_WARP = int(os.environ.get("SHIP_CC_WARP", "30"))
SHIP_CC_YAW = int(os.environ.get("SHIP_CC_YAW", "31"))
SHIP_CC_SMOOTHING_MS = int(os.environ.get("SHIP_CC_SMOOTHING_MS", "250"))
# The cards only show where the engine sorts them after the model (ADR-0107 decision 7:
# items composite by their centres' depth, and the cockpit's centre is nearer than its
# screens), so they are off until cards have depth of their own; the bloom does the glow.
GLOW_CARDS = os.environ.get("GLOW_CARDS", "0") == "1"
GLOW_SCREENS = float(os.environ.get("GLOW_SCREENS", "1.6"))
GLOW_DESK = float(os.environ.get("GLOW_DESK", "4.0"))
PAD_INTENSITY = float(os.environ.get("PAD_INTENSITY", "2.2"))
PAD_RANGE = float(os.environ.get("PAD_RANGE", "1200"))
BLOOM_AT = float(os.environ.get("BLOOM_AT", "0.4" if GLOW else "0.85"))
BLOOM = float(os.environ.get("BLOOM", "0.55" if GLOW else "0.35"))
# The light switches: a group's MIDI CC, from SWITCH_FIRST up on CC_CHANNEL from CC_INPUT,
# fades its lights out over SWITCH_FADE_MS while it is up (SWITCH_UP=off, the default),
# or in (SWITCH_UP=on). A CC reads 0 until it is first sent, so with `off` the cockpit is
# lit until a switch moves. The last CC, the master, fades every group out, so only the
# sky lights the cabin. SWITCHES=0 builds without them.
SWITCHES = os.environ.get("SWITCHES", "1") == "1"
SWITCH_FIRST = int(os.environ.get("SWITCH_FIRST", "40"))
SWITCH_UP = os.environ.get("SWITCH_UP", "off")
SWITCH_FADE_MS = int(os.environ.get("SWITCH_FADE_MS", "2000"))
CC_CHANNEL = int(os.environ.get("CC_CHANNEL", "16"))
CC_INPUT = os.environ.get("CC_INPUT", "Bitwig")
# The groups, in CC order, then the master.
GROUPS = ["cabin", "desk", "screens", "glow"]
SWITCH_CC = {g: SWITCH_FIRST + i for i, g in enumerate(GROUPS + ["master"])}


def geo(cx, cy, w, h, **kw):
    g = {"center": {"x": cx, "y": cy}, "size": {"width": w, "height": h}}
    g.update(kw)
    return g


def src(sid, name, kind, settings):
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": kind}, "settings": settings}


def add(scene, item, source, g, **kw):
    e = {"type": "item.add", "scene_id": scene, "item_id": item, "source_id": source, "geometry": g}
    e.update(kw)
    return e


def flt(owner, fid, kind, settings):
    return {"type": "filter.add", "owner": owner, "chain": "video", "filter_id": fid,
            "kind": kind, "settings": settings}


def must(result, what):
    text, ok = result
    if not ok:
        sys.exit(f"{what} failed")
    return text


def data(mid, prop, key, field, frm, to, smoothing=60, states=None, rng=(0.0, 1.0), curve="linear", **kw):
    """A `data` motion modifier (ADR-0171 decision 3) on `prop`."""
    m = {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "data",
         "input": INPUT, "key": key, "field": field, "range": list(rng), "smoothing_ms": smoothing,
         "curve": curve, "from": frm, "to": to}
    if states:
        m["states"] = states
    m.update(kw)
    return m


def gate(group, prop="opacity", off=-1.0, **kw):
    """The motion modifier with which `group`'s switch fades a light out: `off` added to
    `prop` while the switch is off, nothing while it is on, over SWITCH_FADE_MS."""
    frm, to = (0.0, off) if SWITCH_UP == "off" else (off, 0.0)
    m = {"modifier_id": f"switch_{group}", "property": prop, "enabled": True, "clock": "engine",
         "kind": "midi", "control": "cc", "controller": SWITCH_CC[group], "channel": CC_CHANNEL,
         "input": CC_INPUT, "smoothing_ms": SWITCH_FADE_MS, "curve": "linear", "from": frm, "to": to}
    m.update(kw)
    return m


def gates(group, prop="opacity", off=-1.0, **kw):
    """`group`'s switch and the master's, for one setting: [] without SWITCHES."""
    if not SWITCHES:
        return []
    return [gate(group, prop, off, **kw), gate("master", prop, off, **kw)]


init()
must(op({"type": "canvas.set_size", "width": 1920, "height": 1080}), "canvas")

# ---- the screens: one 1920 x 1080 atlas on the model's `screens` material ----
LAUNCHER_LOOKS = {
    "absent": {"color": "#0d1117", "brightness": 1.0},
    "empty": {"color": "#1a2028", "brightness": 1.0},
    "stopped": {"color": "cell", "brightness": 0.3},
    "playing": {"color": "cell", "brightness": 1.0},
    "recording": {"color": "#ff2a2a", "brightness": 1.0},
    "play": {"color": "cell", "brightness": 1.0, "blink_hz": 4.0},
    "record": {"color": "#ff2a2a", "brightness": 1.0, "blink_hz": 4.0},
    "stop": {"color": "cell", "brightness": 0.6, "blink_hz": 4.0},
}
PAGES_AT = [  # (item, view, x, y, w, h): the model's atlas cells (its README)
    ("a_left", "transport", 0, 0, 640, 360),
    ("a_center", "arrange", 640, 0, 640, 360),
    ("a_right", "device", 1280, 0, 640, 360),
    ("a_ovl", "mixer", 0, 360, 640, 360),
    ("a_ovr", "scenes", 640, 360, 640, 360),
    ("a_side_l", "clip", 1280, 360, 640, 360),
    ("a_side_r", "notes", 1280, 720, 640, 360),
]
ed = [{"type": "scene.create", "scene_id": "atlas", "name": "Screens atlas"},
      src("atlas_bg", "Atlas background", "color", {"color": "#05080cff", "width": 1920, "height": 1080}),
      add("atlas", "a_bg", "atlas_bg", geo(960, 540, 1920, 1080))]


def page(view, width=640):
    """Where a screen's page comes from: inline, with its view and width set ahead of the
    page's script, or from PAGES."""
    if PAGES:
        return {"url": f"{PAGES}/daw.html?view={view}&w={width}"}
    head = f'<head><script>window.DAW_VIEW="{view}";window.DAW_W={width}</script>'
    return {"html": DAW_HTML.replace("<head>", head, 1)}


for item, view, x, y, w, h in PAGES_AT:
    ed += [src("p_" + view, f"DAW {view}", "browser", {
        **page(view), "width": 640, "height": 360, "fps": 30,
        "page_api": True, "page_api_data": True, "page_api_data_input": INPUT}),
        add("atlas", item, "p_" + view, geo(x + w / 2, y + h / 2, w, h, fit_mode="stretch"))]
# The desk: the pads (the selected track's notes, or the clip launcher), the tracks' meters
# and the master's.
if DESK_GRID == "notes":
    ed += [src("launcher", "Note grid", "browser", {
        **page("iso", 600), "width": 600, "height": 360, "fps": 30,
        "page_api": True, "page_api_data": True, "page_api_data_input": INPUT})]
else:
    ed += [src("launcher", "Clip launcher", "grid", {
        "input": INPUT, "mode": "cells", "width": 600, "height": 360, "columns": 8, "rows": 8,
        "columns_key": "track/{column}", "cells_field": "slots", "state_field": "queued,state",
        "color_field": "color", "looks": LAUNCHER_LOOKS, "dim": 0.2, "gap": 6, "radius": 5,
        "background": "#05080cff"})]
# The console's small displays (the launcher panel, the note and density readouts, ...): one
# page, `panels`, in the atlas's free strip right of the desk; the model's live-panel quads
# map its cells (tools/live_panels.py).
PX, PY, PW, PH = PANELS_AT
ed += [src("panels", "Console panels", "browser", {
        **page("panels", PW), "width": PW, "height": PH, "fps": 30,
        "page_api": True, "page_api_data": True, "page_api_data_input": INPUT}),
       add("atlas", "a_panels", "panels", geo(PX + PW / 2, PY + PH / 2, PW, PH, fit_mode="stretch"))]
ed += [
    src("meters", "Track meters", "grid", {
        "input": INPUT, "mode": "bars", "width": 290, "height": 360, "columns": 6, "key": "meters",
        "field": "tracks", "segments": 18, "gap": 8, "radius": 2, "pad": "#11161dff",
        "color_low": "#2fe08aff", "color_high": "#ff4a3aff", "background": "#05080cff"}),
    src("master", "Master meter", "grid", {
        "input": INPUT, "mode": "bars", "width": 56, "height": 360, "columns": 2, "key": "meters",
        "field": "master", "segments": 18, "gap": 6, "radius": 2, "pad": "#11161dff",
        "color_low": "#6ee0ffff", "color_high": "#ffb040ff", "background": "#05080cff"}),
    add("atlas", "a_launcher", "launcher", geo(300, 900, 600, 360)),
    add("atlas", "a_meters", "meters", geo(612 + 145, 900, 290, 360)),
    add("atlas", "a_master", "master", geo(904 + 28, 900, 56, 360)),
    {"type": "source.create", "source_id": "atlas_src", "name": "Screens atlas",
     "kind": {"type": "scene", "scene_id": "atlas"}},
]
if SWITCHES:
    # The screens' switch: a black cover over the whole atlas, clear until it fades in.
    ed += [src("atlas_off", "Screens off", "color", {"color": "#000000ff", "width": 1920, "height": 1080}),
           add("atlas", "a_off", "atlas_off", geo(960, 540, 1920, 1080), opacity=0.0)]
must(batch(ed, "atlas"), "atlas")
if SWITCHES:
    must(op({"type": "item.set_motion", "scene_id": "atlas", "item_id": "a_off",
             "motion": gates("screens", off=1.0)}),
         "screens switch")

# ---- the cockpit ----
cam = SHOTS["cockpit"]
must(batch([
    {"type": "scene.create", "scene_id": "cockpit", "name": "DAW cockpit"},
    src("cockpit_model", "Cockpit", "model", {
        "file": asset(MODEL), "lighting": "scene",
        "texture": {"type": "source", "source_id": "atlas_src"}, "texture_material": "screens"}),
    {"type": "scene.set_camera", "scene_id": "cockpit", "camera": cam},
    add("cockpit", "model", "cockpit_model",
        geo(CX, CY, S * (BOUNDS_MAX[0] - BOUNDS_MIN[0]), S * (BOUNDS_MAX[1] - BOUNDS_MIN[1]), depth_px=0.0)),
], "cockpit"), "cockpit")

# ---- glowing screens: a lit card over each picture on the screens ----
# The model's `screens` material is unlit, so it shows the atlas at most white: the bloom
# never catches it and the probe sees it no brighter than a white wall. A lit card's
# `emissive` adds its picture back up to 4 times, so the screens glow, bloom and light
# the reflections; the desk's grid most of all. Each card shows its picture's own source
# (the engine lights a card only when it shows a source's own frame, not a scene: observed
# behaviour, not an ADR's promise).
if GLOW and GLOW_CARDS:
    from glow import card_at
    ON_SCREENS = [("p_" + view, x, y, w, h, GLOW_SCREENS) for _, view, x, y, w, h in PAGES_AT]
    ON_SCREENS += [("launcher", 0, 720, 600, 360, GLOW_DESK), ("meters", 612, 720, 290, 360, GLOW_DESK),
                   ("master", 904, 720, 56, 360, GLOW_DESK)]
    cards = []
    for sid, x, y, w, h, glow in ON_SCREENS:
        g = card_at(x, y, x + w, y + h)
        g["surface"] = {"lit": True, "roughness": 0.2, "metalness": 0.0, "emissive": glow,
                        "back": "hide", "shadows": False}
        cards.append(add("cockpit", "g_" + sid, sid, g))
    must(batch(cards, "glow"), "glow")
    for sid, *_ in ON_SCREENS:
        if SWITCHES:
            must(op({"type": "item.set_motion", "scene_id": "cockpit", "item_id": "g_" + sid,
                     "motion": gates("screens")}), "screens switch")

THROTTLE = os.path.join(os.path.dirname(MODEL), "throttle.gltf")
if os.path.exists(THROTTLE):
    from shots import THROTTLE_PIVOT, _bounds
    lo, hi = _bounds(THROTTLE)
    mid = p(*[THROTTLE_PIVOT[i] + (lo[i] + hi[i]) / 2 for i in range(3)])
    must(batch([
        src("throttle_model", "Throttle lever", "model", {"file": asset(THROTTLE), "lighting": "scene"}),
        add("cockpit", "throttle", "throttle_model",
            geo(mid["x"], mid["y"], S * (hi[0] - lo[0]), S * (hi[1] - lo[1]), depth_px=mid["z"])),
    ], "throttle"), "throttle")

# The ledge's light bar, where the model ships one (light_bar.gltf): a second model at its
# own place, lit by a small scene, `ledge_bar`, whose middle row it shows along its length
# (u 0.5 over the centre monitor). One white box, `ledge_bar_fill`, centred in that scene
# over black, lights it: its scale is the bar's level, so as it grows from nothing the bar
# lights from the centre outward. Motion on the box's `scale` (from -1, out, to 0, full)
# drives the level; motion on its opacity can switch it.
LIGHT_BAR = os.path.join(os.path.dirname(MODEL), "light_bar.gltf")
if os.path.exists(LIGHT_BAR):
    from shots import _bounds
    lo, hi = _bounds(LIGHT_BAR)
    mid = p(*[(lo[i] + hi[i]) / 2 for i in range(3)])
    must(batch([
        {"type": "scene.create", "scene_id": "ledge_bar", "name": "Ledge light bar"},
        src("ledge_bar_off", "Ledge bar: off", "color", {"color": "#000000ff", "width": 1920, "height": 1080}),
        add("ledge_bar", "ledge_bar_bg", "ledge_bar_off", geo(960, 540, 1920, 1080)),
        src("ledge_bar_on", "Ledge bar: lit", "color", {"color": "#ffffffff", "width": 1920, "height": 1080}),
        add("ledge_bar", "ledge_bar_fill", "ledge_bar_on", geo(960, 540, 1920, 1080)),
        {"type": "source.create", "source_id": "ledge_bar_src", "name": "Ledge light bar",
         "kind": {"type": "scene", "scene_id": "ledge_bar"}},
        src("light_bar_model", "Ledge light bar", "model", {
            "file": asset(LIGHT_BAR), "lighting": "scene",
            "texture": {"type": "source", "source_id": "ledge_bar_src"}, "texture_material": "light_bar"}),
        add("cockpit", "light_bar", "light_bar_model",
            geo(mid["x"], mid["y"], S * (hi[0] - lo[0]), S * (hi[1] - lo[1]), depth_px=mid["z"])),
    ], "light bar"), "light bar")
    # In the DAW cockpit the master's level drives it (ids starting `level`).
    must(op({"type": "item.set_motion", "scene_id": "ledge_bar", "item_id": "ledge_bar_fill",
             "motion": [data("level", "scale", "meters", "master.0", -1.0, 0.0,
                             smoothing=int(os.environ.get("LEVEL_MS", "220")))]}), "light bar level")


def light(lid, name, settings, at, aim=None, size=60):
    q = p(*at)
    g = geo(q["x"], q["y"], size, size, depth_px=q["z"])
    if aim:
        g.update(aim)
    return [src(lid, name, "light", settings), add("cockpit", lid, lid, g)]


L = []
L += light("l_ambient", "Ambient", {"type": "ambient", "color": "#8aa4c8", "intensity": 0.4}, (0, 1.2, 0))
L += light("l_env", "Space sky", {
    "type": "environment", "intensity": 0.9, "backdrop": True, "sky_color": "#070b15",
    "horizon_color": "#131b2c", "ground_color": "#020306", "stars": 0.4, "star_brightness": 1.3,
    "nebula": 0.7, "nebula_color": "#3a1460", "nebula_color_2": "#0d3a5c", "galaxy": 0.7,
    "sky_seed": 4127, "warp": WARP, "warp_ramp_s": 0.0}, (0, 1.2, 0), aim={"turn_deg": SHIP_YAW})
L += light("l_sun", "Starlight", {"type": "directional", "color": "#ffe6c4", "intensity": 2.0,
                                  "shadows": True, "shadow_softness": 0.35},
           (0.6, 3.2, -4.0), aim={"tilt_deg": -35.0, "turn_deg": 192.0 + SHIP_YAW})
L += light("l_cabin", "Cabin", {"type": "point", "color": "#9fc4ff", "intensity": 1.2, "range_px": 3200},
           (0.0, BOUNDS_MAX[1] - 0.1, -0.2))
# A model is lit by at most 8 lights (the ambient and the environment aside), the first
# in stacking order. With GLOW the 8 are the sun, the cabin and the launcher's six pad
# lights, which light the cabin in the band's colours from the desk; without it, the
# screens' glow, a light a track around the cabin and the desk's glow.
if not GLOW:
    L += light("l_glow", "Screen glow", {"type": "point", "color": "#58d6ff", "intensity": 1.0, "range_px": 1100},
               (0.0, 1.0, -1.15))
# The band's lights, each over its track's meter: the kick under the dash, the bass and
# keys on the side consoles, the lead overhead, the echo behind the seat, and the desk's
# glow over the launcher with the master.
TRACK_LIGHTS = [] if GLOW else [
    ("l_kick", "Drums light", "#ff7a1a", (0.0, 0.5, -1.15), 0, 2.6, 1300),
    ("l_hats", "Hats light", "#ffc23d", (-0.55, 1.62, -0.55), 1, 1.2, 900),
    ("l_bass", "Bass light", "#2fd27a", (-0.86, 0.98, -0.25), 2, 2.2, 1100),
    ("l_keys", "Keys light", "#3aa0ff", (0.86, 0.98, -0.25), 3, 2.2, 1100),
    ("l_lead", "Lead light", "#c45cff", (0.0, 1.72, -0.45), 4, 2.4, 1400),
    ("l_echo", "Echo light", "#ff4f9a", (0.0, 1.45, 0.85), 5, 2.8, 2200),
]
for lid, name, color, at, _, inten, rng in TRACK_LIGHTS:
    L += light(lid, name, {"type": "point", "color": color, "intensity": inten, "range_px": rng}, at)
if not GLOW:
    L += light("l_desk", "Desk glow", {"type": "point", "color": "#6ee0ff", "intensity": 1.4, "range_px": 700},
               (0.0, 0.92, -0.86))
# The launcher throws its pads' colours on the desk and the screens above it: a small
# light a track over its column, in the track's colour (the launcher's first 600 px of the
# desk's 960 px cell, the desk 0.72 m wide, so a column is 75 px, 56 mm).
PAD_LIGHTS = []
if GLOW:
    for ti, (_, color) in enumerate([("Drums", "#ff7a1a"), ("Hats", "#ffc23d"), ("Bass", "#2fd27a"),
                                     ("Keys", "#3aa0ff"), ("Lead", "#c45cff"), ("Lead Echo", "#ff4f9a")]):
        x = -0.36 + (ti + 0.5) * 0.05625
        lid = f"l_pad{ti}"
        PAD_LIGHTS.append((lid, ti))
        L += light(lid, f"Pad light {ti + 1}", {"type": "point", "color": color, "intensity": PAD_INTENSITY,
                                                 "range_px": PAD_RANGE}, (x, 0.84, -0.90), size=40)
must(batch(L, "lights"), "lights")

# ---- the data moves the lights ----
# A meter falls to nothing between a drum's hits, eight or sixteen times a bar, so a
# light that follows it fast and all the way down strobes: each light keeps a floor and
# follows the meter over LEVEL_MS, so it swells with the band instead.
LEVEL_MS = int(os.environ.get("LEVEL_MS", "220"))
motion = {lid: [data("level", "opacity", "meters", f"tracks.{ti}.0", -0.5, 0.0, smoothing=LEVEL_MS)]
          for lid, _, _, _, ti, _, _ in TRACK_LIGHTS}
for lid, ti in PAD_LIGHTS:
    motion[lid] = [data("level", "opacity", "meters", f"tracks.{ti}.0", -0.45, 0.0, smoothing=LEVEL_MS)]
if not GLOW:
    motion["l_desk"] = [data("level", "opacity", "meters", "master.0", -0.85, 0.0, smoothing=90)]
    # The screens' glow pulses on every beat: brightest on it, fading through it.
    motion["l_glow"] = [data("beat", "opacity", "clock", "beatPhase", 0.0, -0.6, smoothing=0)]
# The cabin lights come up while the transport plays and go down through the break,
# when only the echo track's clip plays.
motion["l_cabin"] = [data("play", "opacity", "transport", "playing", -0.6, 0.0, smoothing=1200),
                     data("break", "opacity", "track/5", "stopped", -0.85, 0.0, smoothing=1500)]
motion["l_sun"] = [data("break", "opacity", "track/5", "stopped", -0.9, 0.0, smoothing=1500)]
motion["l_ambient"] = [data("break", "opacity", "track/5", "stopped", -0.6, 0.0, smoothing=1500)]
# The sky brightens while either chorus's clip plays on the drums track.
motion["l_env"] = [data(f"chorus{s}", "source", "track/0", f"slots.{s}.state", 0.0, 0.9,
                        smoothing=1800, states={"playing": 1.0}, source={"param": "intensity"}) for s in (2, 5)]
# The ship: the warp drive and the heading, on MIDI CCs from Bitwig (a JTunnel plugin's
# sender, as the camera CCs in import_show.py): SHIP_CC_WARP (30) takes the sky's warp
# from rest to full, and SHIP_CC_YAW (31) turns the ship a whole turn to the right over
# the CC's travel, by spinning the sky and the starlight around the cabin. Each rests
# until its CC first moves (a CC reads 0 until then).
def cc(mid, prop, controller, frm, to, **kw):
    return {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "midi",
            "control": "cc", "controller": controller, "channel": SHIP_CC_CHANNEL, "input": SHIP_CC_INPUT,
            "from": frm, "to": to, "smoothing_ms": SHIP_CC_SMOOTHING_MS, **kw}


motion["l_env"] += [cc("warp", "source", SHIP_CC_WARP, 0.0, 1.0, source={"param": "warp"}),
                    cc("yaw", "turn", SHIP_CC_YAW, 0.0, -360.0)]
motion["l_sun"].append(cc("yaw", "turn", SHIP_CC_YAW, 0.0, -360.0))
# The model's own LEDs and light strips follow the band, by material name: the red LEDs
# the drums, the green the bass, the blue the keys, the amber the master, the orange
# accent strips the lead, and the cabin's light strips pulse on the beat. The amber LEDs'
# and the orange accents' ranges end below 0, a fraction of the file's strength, so they
# don't flare under the bloom's low threshold.
LEDS = [("led_red", "meters", "tracks.0.0", -0.85, 1.6), ("led_green", "meters", "tracks.2.0", -0.85, 1.6),
        ("led_blue", "meters", "tracks.3.0", -0.85, 1.6), ("led_amber", "meters", "master.0", -0.8, -0.45),
        ("glow_amber", "meters", "tracks.4.0", -0.7, -0.1)]
motion["model"] = [data(f"m_{mat}", "source", key, field, frm, to, smoothing=LEVEL_MS * 2 // 3,
                        source={"param": "emissive_strength", "material": mat})
                   for mat, key, field, frm, to in LEDS]
# The cabin's yellow strips stay a soft glow under the low bloom threshold: from 0.45 of
# their own strength on the beat to 0.25 (the file's 2.5 would flare).
motion["model"].append(data("m_strip", "source", "clock", "beatPhase", -0.55, -0.75, smoothing=120,
                            source={"param": "emissive_strength", "material": "light_strip"}))
# ---- the light switches: each light's group, and the master on all of them ----
# A light's strength is its intensity times its opacity, so each switch adds -1 to its
# lights' opacities as it fades off. The glow group's LEDs and strips are the model's
# materials: its 8 motion modifiers are 6 data ones above and these 2, so the glow
# switches drive every material's `emissive_strength` at once, which needs a JStream
# that drives a glow with no material named; an older one leaves the LEDs lit.
LIGHT_GROUP = {"l_ambient": "cabin", "l_sun": "cabin", "l_cabin": "cabin", "l_glow": "desk",
               "l_desk": "desk"}
LIGHT_GROUP.update({lid: "desk" for lid, *_ in TRACK_LIGHTS})
LIGHT_GROUP.update({lid: "desk" for lid, _ in PAD_LIGHTS})
for lid, group in LIGHT_GROUP.items():
    if any(e.get("item_id") == lid for e in L):
        motion.setdefault(lid, []).extend(gates(group))
# The glow's strength multiplies the file's by 1 plus its drives, and the LEDs' data
# drives add up to 1.6, so a switch adds -3 to take it to nothing.
motion["model"] += gates("glow", "source", off=-3.0, source={"param": "emissive_strength"})
for lid, mods in motion.items():
    must(op({"type": "item.set_motion", "scene_id": "cockpit", "item_id": lid, "motion": mods}), f"motion {lid}")

# ---- reflections: the cabin reflects its screens and lights ----
if PROBE:
    c = p(0.0, 1.0, -0.4)
    # An engine without reflection probes (ADR-0170) refuses the kind: build without them.
    _, ok = batch([
        {"type": "scene.set_options", "scene_id": "cockpit", "reflections": True},
        src("probe", "Cabin reflections", "reflection_probe", {
            "width_px": S * 2.4, "height_px": S * 2.1, "depth_px": S * 3.2, "fade_px": 120,
            "resolution": os.environ.get("PROBE_RES", "256"), "refresh_frames": PROBE_EVERY}),
        add("cockpit", "probe", "probe", geo(c["x"], c["y"], 60, 60, depth_px=c["z"])),
    ], "probe")
    if not ok:
        print("no reflection probes in this JStream: built without reflections", file=sys.stderr)

must(batch([flt({"type": "scene", "scene_id": "cockpit"}, "ao", "ambient_occlusion",
                {"radius_px": 60, "strength": 0.8}),
            flt({"type": "scene", "scene_id": "cockpit"}, "bloom", "depth_bloom",
                {"threshold": BLOOM_AT, "strength": BLOOM, "radius_px": 16, "depth_px": 300})], "filters"), "filters")
must(op({"type": "scene.switch", "scene_id": "cockpit"}), "switch")
print("built")
