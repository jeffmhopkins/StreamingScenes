"""The cockpit's small LEDs in four groups, each one channel, `Desk.Lights 1` to `4`, that a
JTunnel Mod drives, gated by the cockpit's Glow and Master switches. The desk itself is
switched off, as the model has it: no note grid, meter bridge or lights following the band.

| Channel | Mod | LEDs (the model's material) |
|---|---|---|
| `desk_lights_1` "Desk.Lights 1" | 21 | the red ones (`led_red`) |
| `desk_lights_2` "Desk.Lights 2" | 22 | the green ones (`led_green`) |
| `desk_lights_3` "Desk.Lights 3" | 23 | the blue ones (`led_blue`) |
| `desk_lights_4` "Desk.Lights 4" | 24 | the amber ones (`led_amber`) |

Each channel is 0 (dark) to 1 (the model's own glow), 1 until its Mod first moves. The
Glow and Master switches still put every LED out, whatever its channel reads. The cabin
lights (the overhead light, the fill and the starlight) are not in any group: the Cabin
switch keeps them. The light strips and the orange accent strips glow steadily, under the
Glow and Master switches.

`Desk lights twinkle` (Ctrl+Alt+G) loops a random twinkle on all four channels, to try
them without Bitwig; `Desk lights steady` (Ctrl+Alt+Shift+G) stops it and brings all four
back to full.

build_daw.py and import_show.py use this for a new build. To change a cockpit already in a
running JStream (a project imported before this), run it:

    python3 desk_lights.py

It adds the channels, the sequences and their keys, puts the model's LEDs on the
channels, removes the desk's lights over the launcher, and points the desk's `grid` slot
at the switched-off pads. MODEL_ITEM (default `model`) names the cockpit's model item.
The readouts' live panels come off the model itself: run
`../tools/trim_live_panels.py` on each copy of the model the project uses.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# (channel, its name, its Mod, the material, the glow-strength drive at 0 and at 1). A
# model's glow strength is the file's times 1 plus its drives, so -1 is dark and 0 the
# file's own. The amber LEDs stop at a little over half, as they did under the meters,
# so the many of them don't flare under the bloom's low threshold.
GROUPS = [
    ("desk_lights_1", "Desk.Lights 1", 21, "led_red", -1.0, 0.0),
    ("desk_lights_2", "Desk.Lights 2", 22, "led_green", -1.0, 0.0),
    ("desk_lights_3", "Desk.Lights 3", 23, "led_blue", -1.0, 0.0),
    ("desk_lights_4", "Desk.Lights 4", 24, "led_amber", -1.0, -0.45),
]
# The strips that glow steadily: (material, drive), the light strips at 0.35 of the file's
# 2.5 and the orange accents at 0.6 of its 1.6, both under the bloom's low threshold.
STEADY = [("light_strip", -0.65), ("glow_amber", -0.4)]
# The desk's grid controller switched off: the model's own placeholder of dark pads.
PADS_OFF = os.path.join(HERE, "desk", "pads-off.png")

TWINKLE_MS = 12_000
TWINKLE_SEED = 7
STEADY_MS = 400
KEYS = [("Desk lights twinkle", "KeyG", "desk_twinkle"),
        ("Desk lights steady", "Shift+KeyG", "desk_steady")]


def channels(mod_inputs):
    """The four channels' `channel.set`s. `mod_inputs(n)` is the list of inputs reading
    JTunnel Mod n ([] for none)."""
    return [{"type": "channel.set", "channel": {
        "channel_id": cid, "name": name, "default": 1.0, "inputs": mod_inputs(mod)}}
        for cid, name, mod, *_ in GROUPS]


def _drive(mid, channel, material, at0, at1, smoothing=60):
    return {"modifier_id": mid, "property": "source", "enabled": True, "clock": "engine",
            "kind": "channel", "channel_id": channel, "smoothing_ms": smoothing, "curve": "linear",
            "from": at0, "to": at1, "source": {"param": "emissive_strength", "material": material}}


def model_motion(gates):
    """The model item's motion: each LED group on its channel, the strips steady, and
    `gates` (the Glow and Master switches on every material's glow strength) after them.
    The strips' level rides on `power_glow`, at 0 while it is off, so it costs no slot of
    its own beyond the gates; 4 + 2 + 2 modifiers."""
    out = [_drive(f"m_{cid}", cid, mat, a0, a1) for cid, _, _, mat, a0, a1 in GROUPS]
    out += [_drive(f"m_{mat}", "power_glow", mat, -1.0, level, smoothing=0) for mat, level in STEADY]
    return out + list(gates)


def twinkle_points(rng):
    """One channel's twinkle over a pass: mostly lit, dipping and flashing at random, each
    change quick, so the group sparkles. Starts and ends at full, so it loops seamlessly."""
    pts, t = [], 0
    while True:
        t += rng.randint(120, 900)
        if t >= TWINKLE_MS - 200:
            break
        v = rng.choice([1.0, 1.0, 0.85, 0.6, 0.35, 0.1, 0.0])
        pts.append({"at_ms": t, "value": v, "curve": "linear" if v > 0.5 else "ease_out"})
    pts.append({"at_ms": TWINKLE_MS, "value": 1.0, "curve": "linear"})
    return pts


def timelines():
    """`Desk lights twinkle`, a loop, and `Desk lights steady`, which stops it."""
    rng = random.Random(TWINKLE_SEED)
    twinkle = {"timeline_id": "desk_twinkle", "name": "Desk lights twinkle", "duration_ms": TWINKLE_MS,
               "loop": "loop",
               "stops": [{"type": "timeline", "timeline_id": "desk_steady", "edge": "starts"}],
               "lanes": [{"target": {"channel": cid}, "points": twinkle_points(rng)}
                         for cid, *_ in GROUPS]}
    steady = {"timeline_id": "desk_steady", "name": "Desk lights steady", "duration_ms": STEADY_MS,
              "lanes": [{"target": {"channel": cid},
                         "points": [{"at_ms": STEADY_MS, "value": 1.0, "curve": "ease_out"}]}
                        for cid, *_ in GROUPS]}
    return [twinkle, steady]


def sequences(scene="cockpit"):
    """The sequences on `scene` and their hotkeys (Ctrl+Alt+G, Ctrl+Alt+Shift+G)."""
    return ([{"type": "timeline.set", "scene_id": scene, "timeline": t} for t in timelines()]
            + [{"type": "hotkey.set", "chord": "Ctrl+Alt+" + key,
                "action": {"type": "timeline.play", "timeline_id": tid}} for _, key, tid in KEYS])


def pads_off_source(asset):
    return {"type": "source.create", "source_id": "desk_pads_off", "name": "Desk pads, switched off",
            "kind": {"type": "builtin", "kind": "image"}, "settings": {"file": asset(PADS_OFF)}}


# ---- changing a cockpit already in a running JStream ----

# What the desk had: its lit pads, meter bridge and their unlit pages, and the lights over it.
OLD_DESK_ITEMS = ["src_desk_grid_launcher_unlit", "src_desk_grid_bridge_unlit",
                  "src_desk_grid_launcher", "src_desk_grid_bridge"]
OLD_LIGHTS = [f"l_pad{n}" for n in range(5)]


def _main():
    sys.path.insert(0, os.path.join(HERE, "..", "jstream"))
    from mcp import asset, batch, init, op
    import sources
    from sources import DESK, DESK_H, W, H, channel, sequence, _shows

    def mods(n):
        return [{"kind": "data", "key": "params", "field": f"values.{n - 1}", "range": [0.0, 1.0],
                 "smoothing_ms": 30, "curve": "linear", "from": 0.0, "to": 1.0}]

    def follow(group, off):
        return {"modifier_id": f"switch_{group}", "property": "opacity", "enabled": True,
                "clock": "engine", "kind": "channel", "channel_id": "power_" + group, "smoothing_ms": 30,
                "curve": "linear", "from": off, "to": 0.0}

    def glow_gate(group):
        m = follow(group, -3.0)
        m.update(property="source", source={"param": "emissive_strength"})
        return m

    def step(edits, what):
        _, ok = batch(edits, what)
        print(("done: " if ok else "FAILED: ") + what)
        return ok

    init()
    model = os.environ.get("MODEL_ITEM", "model")
    step(channels(mods), "Desk.Lights 1 to 4 channels, on JTunnel Mods 21 to 24")
    step([{"type": "item.set_motion", "scene_id": "cockpit", "item_id": model,
           "motion": model_motion([glow_gate("glow"), glow_gate("master")])}],
         f"the LEDs on the channels (item `{model}`)")
    step(sequences(), "the twinkle and steady sequences, Ctrl+Alt+G and Ctrl+Alt+Shift+G")
    for lid in OLD_LIGHTS:
        step([{"type": "item.remove", "item_id": lid}, {"type": "source.delete", "source_id": lid}],
             f"remove the desk light {lid}")
    # The desk's grid slot: the switched-off pads, dimmed by the lights as the unlit pads were.
    dx, dy, dw, dh = DESK
    top = (H - DESK_H) / 2
    item = channel("desk", "grid") + "_desk_pads_off"
    feed = channel("desk", "feed")
    desk = [pads_off_source(asset)]
    desk += [{"type": "item.remove", "item_id": i} for i in OLD_DESK_ITEMS]
    desk += [{"type": "item.add", "scene_id": "src_desk", "item_id": item, "source_id": "desk_pads_off",
              "geometry": {"center": {"x": W / 2, "y": top + DESK_H / 2}, "size": {"width": W, "height": DESK_H},
                           "fit_mode": "stretch"}},
             {"type": "item.reorder", "item_id": item, "index": 0},
             {"type": "item.set_motion", "scene_id": "src_desk", "item_id": item,
              "motion": [follow("cabin", -0.5), follow("desk", -1.0), follow("master", -1.0)]}]
    members = {"grid": [item], "feed": [feed]}
    desk.append({"type": "channel.set", "channel": {
        "channel_id": channel("desk", "grid"), "name": "Desk." + sources.DESK_SLOTS[0][1], "default": 1.0}})
    for slot, name, _ in sources.DESK_SLOTS:
        lanes = [{"target": {"channel": channel("desk", o)},
                  "points": [{"at_ms": sources.FADE_MS, "value": 1.0 if o == slot else 0.0, "curve": "linear"}]}
                 for o, _, _ in sources.DESK_SLOTS]
        desk.append({"type": "timeline.set", "scene_id": "src_desk", "timeline": {
            "timeline_id": sequence("desk", slot), "name": f"Desk: {name}", "duration_ms": sources.FADE_MS,
            "lanes": lanes,
            "cues": _shows("src_desk", [(i, o == slot) for o, _, _ in sources.DESK_SLOTS for i in members[o]])}})
    step(desk, "the desk's pads switched off (its grid slot)")
    # Its old sources, left with nothing showing them on the desk; the 2D desk keeps its own.
    print("done. The note grid and meter bridge sources stay for the DAW desk 2D scene.")


if __name__ == "__main__":
    _main()
