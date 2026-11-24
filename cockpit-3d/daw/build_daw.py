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
INPUT = os.environ.get("DAW_INPUT", "")
PROBE = os.environ.get("PROBE", "1") == "1"
PROBE_EVERY = int(os.environ.get("PROBE_EVERY", "10"))
GLOW = os.environ.get("GLOW", "1") == "1"
# The desk's 8 x 8 pads: `notes` (the default) plays the selected track as an isomorphic
# note grid, rows a fourth apart, from the page's `iso` view; `clips` is the clip launcher.
DESK_GRID = os.environ.get("DESK_GRID", "notes")
# The ship (see the ship's rig below): its heading, pitch (nose up) and roll (right wing
# down) at rest in degrees, its warp at rest (0 to 1), and the MIDI CCs that drive them.
SHIP_YAW = float(os.environ.get("SHIP_YAW", "0"))
SHIP_PITCH = float(os.environ.get("SHIP_PITCH", "0"))
SHIP_ROLL = float(os.environ.get("SHIP_ROLL", "0"))
WARP = float(os.environ.get("WARP", "0"))
SHIP_CC_CHANNEL = int(os.environ.get("SHIP_CC_CHANNEL", "16"))
SHIP_CC_INPUT = os.environ.get("SHIP_CC_INPUT", "")
SHIP_CC_WARP = int(os.environ.get("SHIP_CC_WARP", "30"))
SHIP_CC_YAW = int(os.environ.get("SHIP_CC_YAW", "31"))
SHIP_CC_PITCH = int(os.environ.get("SHIP_CC_PITCH", "32"))
SHIP_CC_ROLL = int(os.environ.get("SHIP_CC_ROLL", "33"))
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
# sky lights the cabin. SWITCHES=0 builds without them. With channels (below) every switch
# starts on whatever SWITCH_UP says, since a CC only counts once it moves, and SWITCHES=0
# leaves out only the CCs.
# In a JStream with channels (ADR-0183, protocol 0.169) each switch is a channel,
# `power_<group>` (1 on, 0 off), that its CC is one input of, so a sequence (ADR-0184,
# import_show.py's) can switch the same lights; `screen_<cell>` is a channel a monitor,
# following `power_screens`, so a sequence can light the monitors one at a time, and `warp`
# carries the warp CC the same way. CHANNELS=0 keeps the CCs on the lights directly.
CHANNELS = os.environ.get("CHANNELS", "1") == "1"
# With channels, the controls a person plays are also a JTunnel sender's modulation params
# (Mod 1 to Mod 32, the `params` key's `values.N`, read from MOD_INPUT, default DAW_INPUT):
# each channel reads its Mod as one more input, and JStream names the Mod after the channel
# (ADR-0181), so the Mod list in the JTunnel plugin in Bitwig says what each one does.
# MODS=0 leaves them out.
MODS = os.environ.get("MODS", "1") == "1"
MOD_INPUT = os.environ.get("MOD_INPUT", "")
MOD = {  # channel: its Mod number. 1 on and 0 off for the switches, 1 full for the warp.
    "power_master": 1, "power_cabin": 2, "power_desk": 3, "power_glow": 4, "power_screens": 5,
    "warp": 6, "holo": 7, "ship_yaw": 8, "ship_pitch": 9, "ship_roll": 10,
    "screen_center": 11, "screen_left": 12, "screen_right": 13, "screen_ovl": 14,
    "screen_ovr": 15, "screen_side_l": 16, "screen_side_r": 17, "screen_desk": 18,
    "screen_panels": 19,
}
SWITCHES = os.environ.get("SWITCHES", "1") == "1"
SWITCH_FIRST = int(os.environ.get("SWITCH_FIRST", "40"))
SWITCH_UP = os.environ.get("SWITCH_UP", "off")
SWITCH_FADE_MS = int(os.environ.get("SWITCH_FADE_MS", "2000"))
CC_CHANNEL = int(os.environ.get("CC_CHANNEL", "16"))
CC_INPUT = os.environ.get("CC_INPUT", "")
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


def _input(name):
    """The `input` field naming the sender `name`, or none at all, which reads any sender
    (or, in the desktop app, the live one)."""
    return {"input": name} if name else {}


def data(mid, prop, key, field, frm, to, smoothing=60, states=None, rng=(0.0, 1.0), curve="linear", **kw):
    """A `data` motion modifier (ADR-0171 decision 3) on `prop`."""
    m = {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "data",
         **_input(INPUT), "key": key, "field": field, "range": list(rng), "smoothing_ms": smoothing,
         "curve": curve, "from": frm, "to": to}
    if states:
        m["states"] = states
    m.update(kw)
    return m


def follow(mid, prop, channel, at0, at1, smoothing=30, **kw):
    """A `channel` motion modifier (ADR-0183 decision 5): `at0` added to `prop` while the
    channel reads 0, `at1` while it reads 1."""
    m = {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "channel",
         "channel_id": channel, "smoothing_ms": smoothing, "curve": "linear", "from": at0, "to": at1}
    m.update(kw)
    return m


def cc_input(controller, at0, at1, smoothing, channel=CC_CHANNEL, sender=CC_INPUT):
    """A channel's input reading a MIDI CC: `at0` at 0 and `at1` at 127, as channel values."""
    return {"kind": "midi", "control": "cc", "controller": controller, "channel": channel,
            **_input(sender), "smoothing_ms": smoothing, "curve": "linear", "from": at0, "to": at1}


def mod_inputs(channel, smoothing=30):
    """`channel`'s JTunnel Mod as a list of one input, 0 to 1 onto 0 to 1: [] without one."""
    if not MODS or channel not in MOD:
        return []
    return [{"kind": "data", **_input(MOD_INPUT or INPUT), "key": "params",
             "field": f"values.{MOD[channel] - 1}", "range": [0.0, 1.0], "smoothing_ms": smoothing,
             "curve": "linear", "from": 0.0, "to": 1.0}]


def gate(group, prop="opacity", off=-1.0, **kw):
    """The motion modifier with which `group`'s switch fades a light out: `off` added to
    `prop` while the switch is off, nothing while it is on, over SWITCH_FADE_MS."""
    if CHANNELS:
        return follow(f"switch_{group}", prop, "power_" + group, off, 0.0, **kw)
    frm, to = (0.0, off) if SWITCH_UP == "off" else (off, 0.0)
    m = {"modifier_id": f"switch_{group}", "property": prop, "enabled": True, "clock": "engine",
         "kind": "midi", "control": "cc", "controller": SWITCH_CC[group], "channel": CC_CHANNEL,
         **_input(CC_INPUT), "smoothing_ms": SWITCH_FADE_MS, "curve": "linear", "from": frm, "to": to}
    m.update(kw)
    return m


def gates(group, prop="opacity", off=-1.0, **kw):
    """`group`'s switch and the master's, for one setting: [] without SWITCHES or channels."""
    if not SWITCHES and not CHANNELS:
        return []
    return [gate(group, prop, off, **kw), gate("master", prop, off, **kw)]


init()
must(op({"type": "canvas.set_size", "width": 1920, "height": 1080}), "canvas")

# ---- the switches as channels: each on (1) until its CC or a sequence turns it off ----
if CHANNELS:
    # The CC's travel as the channel's value: up is off with SWITCH_UP=off. The input only
    # counts once the CC first moves, so the lights start on.
    up, down = (0.0, 1.0) if SWITCH_UP == "off" else (1.0, 0.0)
    chans = [{"channel_id": "power_" + g, "name": f"{g.title()} power", "default": 1.0,
              "inputs": ([cc_input(SWITCH_CC[g], down, up, SWITCH_FADE_MS)] if SWITCHES else [])
              + mod_inputs("power_" + g, SWITCH_FADE_MS)}
             for g in GROUPS + ["master"]]
    _, CHANNELS = batch([{"type": "channel.set", "channel": c} for c in chans], "power channels")
    if not CHANNELS:
        print("no channels in this JStream (protocol 0.169): the switches stay on their CCs",
              file=sys.stderr)

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
# With channels, each monitor has a black cover of its own, clear while its `screen_<cell>`
# channel is on; the channel follows `power_screens`, so the screens' CC still switches
# them all, and a sequence can switch them one by one. Without, one cover over the atlas.
SCREEN_CELLS = [(item[2:], x, y, w, h) for item, _, x, y, w, h in PAGES_AT]
SCREEN_CELLS += [("desk", 0, 720, 960, 360), ("panels", PX, PY, PW, PH)]
if CHANNELS:
    ed += [src("atlas_off", "Screens off", "color", {"color": "#000000ff", "width": 64, "height": 64})]
    ed += [add("atlas", "off_" + cell, "atlas_off", geo(x + w / 2, y + h / 2, w, h, fit_mode="stretch"),
               opacity=0.0) for cell, x, y, w, h in SCREEN_CELLS]
elif SWITCHES:
    # The screens' switch: a black cover over the whole atlas, clear until it fades in.
    ed += [src("atlas_off", "Screens off", "color", {"color": "#000000ff", "width": 1920, "height": 1080}),
           add("atlas", "a_off", "atlas_off", geo(960, 540, 1920, 1080), opacity=0.0)]
must(batch(ed, "atlas"), "atlas")
if CHANNELS:
    ch = [{"type": "channel.set", "channel": {
        "channel_id": "screen_" + cell, "name": f"Screen {cell.replace('_', ' ')}", "default": 1.0,
        "inputs": [{"kind": "channel", "channel_id": "power_screens", "smoothing_ms": 0,
                    "curve": "linear", "from": 0.0, "to": 1.0}] + mod_inputs("screen_" + cell)}}
        for cell, *_ in SCREEN_CELLS]
    ch += [{"type": "item.set_motion", "scene_id": "atlas", "item_id": "off_" + cell,
            "motion": [follow("screen", "opacity", "screen_" + cell, 1.0, 0.0),
                       gate("master", off=1.0)]} for cell, *_ in SCREEN_CELLS]
    must(batch(ch, "screen channels"), "screen channels")
elif SWITCHES:
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
    # With channels each card follows its own monitor's channel, as its cover does.
    CELL_OF = {"p_" + view: item[2:] for item, view, *_ in PAGES_AT}
    for sid, *_ in ON_SCREENS:
        if CHANNELS:
            gate_list = [follow("screen", "opacity", "screen_" + CELL_OF.get(sid, "desk"), -1.0, 0.0),
                         gate("master")]
        else:
            gate_list = gates("screens")
        if gate_list:
            must(op({"type": "item.set_motion", "scene_id": "cockpit", "item_id": "g_" + sid,
                     "motion": gate_list}), "screens switch")


def light(lid, name, settings, at, aim=None, size=60, scene="cockpit"):
    q = p(*at)
    g = geo(q["x"], q["y"], size, size, depth_px=q["z"])
    if scene != "cockpit":
        # In the ship's rig: the group's canvas centre is the rig's pivot (see below).
        g["center"] = {"x": q["x"] - RIG_AT["x"] + 960, "y": q["y"] - RIG_AT["y"] + 540}
        g["depth_px"] = q["z"] - RIG_AT["z"]
    if aim:
        g.update(aim)
    return [src(lid, name, "light", settings), add(scene, lid, lid, g)]


# The ship's rig: the sky and the starlight turn around the cabin as the ship turns, inside
# three nested 3D groups (ADR-0164: a child's orientation is its group's followed by its
# own, and lights in a 3D group light the whole scene). The outer group rolls, the middle
# one pitches and the inner one yaws, so the sky turns by the inverse of the ship's
# heading, then pitch, then roll, as an aircraft's. Each group pivots on the pilot's seat.
# A group's tilt tips its top away from the cabin's camera, so a positive tilt brings the
# sky's zenith forward (the nose up); its rotation turns it clockwise on screen, so the
# sky turns the other way to the ship's roll (SHIP_ROLL is to the right, rotation_deg
# its negative).
# The sky follows its item's tilt and rotation with a JStream from ADR-0182 on; an older
# one turns it on the heading only.
RIG_AT = p(0, 1.2, 0)
RIG = [("ship_roll", "Ship roll", {"rotation_deg": -SHIP_ROLL}),
       ("ship_pitch", "Ship pitch", {"tilt_deg": SHIP_PITCH}),
       ("ship_yaw", "Ship heading", {"turn_deg": SHIP_YAW})]
SHIP = RIG[-1][0]


def rig():
    out, parent = [], "cockpit"
    for gid, name, pose in RIG:
        out += [{"type": "scene.create", "scene_id": gid, "name": name, "role": "group"},
                {"type": "scene.set_options", "scene_id": gid, "share_space": True},
                {"type": "source.create", "source_id": gid, "name": name,
                 "kind": {"type": "scene", "scene_id": gid}, "settings": {}}]
    for gid, name, pose in RIG:
        at = RIG_AT if parent == "cockpit" else {"x": 960, "y": 540, "z": 0.0}
        out.append(add(parent, gid, gid, geo(at["x"], at["y"], 1920, 1080, depth_px=at["z"], **pose)))
        parent = gid
    return out


L = []
L += light("l_ambient", "Ambient", {"type": "ambient", "color": "#8aa4c8", "intensity": 0.4}, (0, 1.2, 0))
L += rig()
L += light("l_env", "Space sky", {
    "type": "environment", "intensity": 0.9, "backdrop": True, "sky_color": "#070b15",
    "horizon_color": "#131b2c", "ground_color": "#020306", "stars": 0.4, "star_brightness": 1.3,
    "nebula": 0.7, "nebula_color": "#3a1460", "nebula_color_2": "#0d3a5c", "galaxy": 0.7,
    "sky_seed": 4127, "warp": WARP, "warp_ramp_s": 0.0}, (0, 1.2, 0), scene=SHIP)
L += light("l_sun", "Starlight", {"type": "directional", "color": "#ffe6c4", "intensity": 2.0,
                                  "shadows": True, "shadow_softness": 0.35},
           (0.6, 3.2, -4.0), aim={"tilt_deg": -35.0, "turn_deg": 192.0}, scene=SHIP)
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
# The warp goes where the ship points (JStream ADR-0187): each jump travels straight ahead
# from wherever the heading, pitch and roll have turned the sky, and at warp they swing it
# at most WARP_LOOK_DEG; out of warp the sky stays put and they turn it from there.
# WARP_AIM=sky streams along the sky's own axis, as before. An engine without the setting
# keeps the sky's axis.
WARP_AIM = os.environ.get("WARP_AIM", "ahead")
if WARP_AIM not in ("ahead", "sky"):
    print(f"WARP_AIM={WARP_AIM!r} is neither `ahead` nor `sky`: using `sky`", file=sys.stderr)
WARP_LOOK_DEG = float(os.environ.get("WARP_LOOK_DEG", "10"))
if WARP_AIM == "ahead":
    _, ok = op({"type": "source.set_settings", "source_id": "l_env",
                "patch": {"warp_aim": "ahead", "warp_look_deg": WARP_LOOK_DEG}})
    if not ok:
        print("this JStream has no warp_aim (ADR-0187): the warp streams along the sky's axis",
              file=sys.stderr)
# Where a warp arrives (JStream ADR-0188): a picture in the sky ahead as each warp drops
# out, a nebula, a galaxy, a black hole or a planet, a different one each time
# (sky_arrivals.py). SUNS=1 gives each planet its star, off to one side, to turn and find
# (needs ADR-0198's companions). ARRIVALS=0 leaves the sky as it was. An engine without
# them refuses the settings, and nothing of them is left.
ARRIVALS = os.environ.get("ARRIVALS", "1") == "1"
SUNS = os.environ.get("SUNS", "0") == "1"
ARRIVAL_LIGHT = float(os.environ.get("ARRIVAL_LIGHT", "0.6"))
if ARRIVALS:
    sys.path.insert(0, HERE)
    import sky_arrivals
    # One batch, so an engine that refuses the settings is left with no `arrivals` scene.
    _, ok = batch(sky_arrivals.edits(SUNS) + [{"type": "source.set_settings", "source_id": "l_env",
                                                "patch": sky_arrivals.patch(ARRIVAL_LIGHT)}],
                  "arrival pictures")
    if not ok:
        print("this JStream has no sky_pictures (ADR-0188): no arrival pictures", file=sys.stderr)

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
# The ship: the warp drive, heading, pitch and roll, on MIDI CCs from Bitwig (a JTunnel
# plugin's sender, as the camera CCs in import_show.py): SHIP_CC_WARP (30) takes the sky's
# warp from rest to full, and SHIP_CC_YAW (31), SHIP_CC_PITCH (32) and SHIP_CC_ROLL (33)
# each turn the ship a whole turn over the CC's travel (to the right, nose up and right
# wing down), by turning the rig's groups and with them the sky and the starlight. Each
# rests until its CC first moves (a CC reads 0 until then).
def cc(mid, prop, controller, frm, to, **kw):
    return {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "midi",
            "control": "cc", "controller": controller, "channel": SHIP_CC_CHANNEL, **_input(SHIP_CC_INPUT),
            "from": frm, "to": to, "smoothing_ms": SHIP_CC_SMOOTHING_MS, **kw}


if CHANNELS:
    # The warp is a channel the CC is one input of, so a sequence can jump to warp too.
    must(op({"type": "channel.set", "channel": {
        "channel_id": "warp", "name": "Warp", "default": 0.0,
        "inputs": [cc_input(SHIP_CC_WARP, 0.0, 1.0, SHIP_CC_SMOOTHING_MS,
                            channel=SHIP_CC_CHANNEL, sender=SHIP_CC_INPUT)]
        + mod_inputs("warp", SHIP_CC_SMOOTHING_MS)}}), "warp channel")
    motion["l_env"].append(follow("warp", "source", "warp", 0.0, 1.0, source={"param": "warp"}))
    # The heading, pitch and roll too: a whole turn over the channel's 0 to 1, from rest.
    ship = [("ship_yaw", "Ship heading", SHIP_CC_YAW, "turn", -360.0),
            ("ship_pitch", "Ship pitch", SHIP_CC_PITCH, "tilt", 360.0),
            ("ship_roll", "Ship roll", SHIP_CC_ROLL, "rotation", -360.0)]
    must(batch([{"type": "channel.set", "channel": {
        "channel_id": cid, "name": name, "default": 0.0,
        "inputs": [cc_input(ccn, 0.0, 1.0, SHIP_CC_SMOOTHING_MS, channel=SHIP_CC_CHANNEL,
                            sender=SHIP_CC_INPUT)] + mod_inputs(cid, SHIP_CC_SMOOTHING_MS)}}
        for cid, name, ccn, _, _ in ship], "ship channels"), "ship channels")
    for cid, _, _, prop, turn in ship:
        motion[cid] = [follow(cid[5:], prop, cid, 0.0, turn)]
else:
    motion["l_env"].append(cc("warp", "source", SHIP_CC_WARP, 0.0, 1.0, source={"param": "warp"}))
if not CHANNELS:
    motion["ship_yaw"] = [cc("yaw", "turn", SHIP_CC_YAW, 0.0, -360.0)]
    motion["ship_pitch"] = [cc("pitch", "tilt", SHIP_CC_PITCH, 0.0, 360.0)]
    motion["ship_roll"] = [cc("roll", "rotation", SHIP_CC_ROLL, 0.0, -360.0)]
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
    scene = {"l_env": SHIP, "l_sun": SHIP, "ship_pitch": "ship_roll", "ship_yaw": "ship_pitch"}.get(lid, "cockpit")
    must(op({"type": "item.set_motion", "scene_id": scene, "item_id": lid, "motion": mods}), f"motion {lid}")

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
