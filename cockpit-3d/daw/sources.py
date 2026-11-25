"""What the cockpit's three main monitors and its hologram show, each switchable: every one
shows a subscene of its own (a scene placed as a source, listed in the Scenes panel's
`Monitor sources` folder), and the subscene holds one
item per source it can show, so switching is a sequence that fades one item in and the
others out. The selected source's soft key under the screen lights.

    import sources; batch(sources.edits(...))   # import_show.py does this

The subscenes, `src_left`, `src_center`, `src_right` and `src_holo`, each hold five items,
one per soft key, left to right:

| Key | Source | On every monitor and the hologram |
|---|---|---|
| 1 | `p_transport` | the transport page |
| 2 | `p_arrange` | the arrangement page |
| 3 | `p_device` | the device page |
| 4 | `p_mixer` | the mixer page |
| 5 | `feed` (`holo_feed` on the hologram) | a camera feed: a stand-in still until a person points the item at a webcam or a capture |

The left monitor starts on the transport, the centre on the arrangement, the right on the
device, and the hologram on its feed, as before. Because the screen is just the subscene,
a person customises it as any scene: toggle an item's visibility in the app, point an
item (`src_<screen>_<slot>`) at another source, or add, move and layer items of their own.

A sequence a slot, `<screen>_<slot>` ("Centre monitor: Mixer"), runs `item.show` on that
slot's item and `item.hide` on the other four at its start, and takes the screen's five
channels, `src_<screen>_<slot>` (1 selected, 0 not), to that slot in FADE_MS (150); the
channels only light the keys. Items a person adds are left alone by the keys. Showing or
hiding an item by hand doesn't move the key lights. Play one from the app's sequences, a
hotkey (KEYS: Ctrl+Alt+Shift with 1 to 5 for the left monitor, 6 to 0 the centre, Y to
P the right and Z to B the hologram), a MIDI note (import_show.py's NOTES), a show cue or
an agent's `timeline.play`.

The keys' lights are the model's `softkey_lights` (cockpit-3d/tools/softkeys.py): a quad
on each key's face maps one block of the screens atlas's key strip, so a lit block in the
atlas lights its key. The atlas holds a dim strip of unlit keys there and, over it, a lit
block per key, which follows the key's slot channel, the glow switch and the master: the
keys are LEDs, so the Glow and Master switches darken them as they do the others.

The desk's grid controller has a subscene too, `src_desk` (desk_edits()): its pads and
meter bridge, or a camera feed (`desk_feed`) over the whole 8:3 surface, on
Ctrl+Alt+Shift+N and K. It has no keys to light.

Everything here is generic JStream: scenes as sources, scene folders, item visibility, channels,
sequences with cues and lanes, hotkeys and `channel` motion modifiers.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import softkeys  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))
from mcp import asset  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
STANDIN = os.path.join(ROOT, "starship-cockpit", "pages", "caller.png")
FADE_MS = int(os.environ.get("SOURCE_FADE_MS", "150"))
KEY_LIT = os.environ.get("KEY_LIT", "#ffb347ff")
KEY_UNLIT = os.environ.get("KEY_UNLIT", "#2a2219ff")

# (slot, its name, its source); the feed's source is per screen (FEED below).
SLOTS = [("transport", "Transport", "p_transport"), ("arrange", "Arrangement", "p_arrange"),
         ("device", "Device", "p_device"), ("mixer", "Mixer", "p_mixer"),
         ("feed", "Camera feed", None)]
# (screen, its name, the atlas item or hologram card that shows it, the slot it starts on,
# the keys after Ctrl+Alt+Shift, one a slot)
SCREENS = [
    ("left", "Left monitor", "a_left", "transport", ["Digit1", "Digit2", "Digit3", "Digit4", "Digit5"]),
    ("center", "Centre monitor", "a_center", "arrange", ["Digit6", "Digit7", "Digit8", "Digit9", "Digit0"]),
    ("right", "Right monitor", "a_right", "device", ["KeyY", "KeyU", "KeyI", "KeyO", "KeyP"]),
    ("holo", "Hologram", "holo_card", "feed", ["KeyZ", "KeyX", "KeyC", "KeyV", "KeyB"]),
]
FEED = {"left": "feed", "center": "feed", "right": "feed", "holo": "holo_feed"}
W, H = 1920, 1080


def channel(screen, slot):
    return f"src_{screen}_{slot}"


def sequence(screen, slot):
    return f"{screen}_{slot}"


def action(screen, slot):
    return {"type": "timeline.play", "timeline_id": sequence(screen, slot)}


def controls(hologram=True):
    """What a person plays, in note order: [(name, key chord, action)], each screen's five
    slots in turn (the hologram's only with `hologram`)."""
    out = []
    for screen, name, _, _, keys in SCREENS:
        if screen == "holo" and not hologram:
            continue
        for (slot, sname, _), key in zip(SLOTS, keys):
            out.append((f"{name}: {sname}", "Ctrl+Alt+Shift+" + key, action(screen, slot)))
    return out


def _follow(ch):
    return {"modifier_id": "source", "property": "opacity", "enabled": True, "clock": "engine",
            "kind": "channel", "channel_id": ch, "smoothing_ms": 0, "curve": "linear",
            "from": -1.0, "to": 0.0}


def _shows(sid, items):
    """A sequence's cues at its start: show each (item, True) and hide each (item, False)
    in subscene `sid`."""
    return [{"at_ms": 0, "action": {"type": "item.show" if shown else "item.hide",
                                    "item_id": item, "scene_id": sid}} for item, shown in items]


def edits(hologram=True, gates=(), unlit_gates=()):
    """The subscenes, their channels and sequences, the hotkeys, the key lights in the
    `atlas` scene, and the screens pointed at the subscenes. `gates` are more motion
    modifiers for every lit key (build_daw.py's glow and master switches), `unlit_gates` for
    the strip of unlit keys (the switches that dim the desk's unlit pads)."""
    e = [{"type": "source.create", "source_id": "feed",
          "name": "Monitor camera feed (swap for a camera or capture)",
          "kind": {"type": "builtin", "kind": "image"},
          "settings": {"file": asset(STANDIN)}}]
    keys = []
    for screen, name, shown_on, start, chords in SCREENS:
        if screen == "holo" and not hologram:
            continue
        sid = "src_" + screen
        e += [{"type": "scene.create", "scene_id": sid, "name": f"{name} source"},
              {"type": "source.create", "source_id": sid, "name": f"{name} source",
               "kind": {"type": "scene", "scene_id": sid}, "settings": {}}]
        for slot, sname, source in SLOTS:
            ch = channel(screen, slot)
            e += [{"type": "channel.set", "channel": {
                      "channel_id": ch, "name": f"{name}: {sname}",
                      "default": 1.0 if slot == start else 0.0}},
                  {"type": "item.add", "scene_id": sid, "item_id": ch,
                   "source_id": source or FEED[screen],
                   "geometry": {"center": {"x": W / 2, "y": H / 2}, "size": {"width": W, "height": H},
                                "fit_mode": "fill" if slot == "feed" else "stretch"}},
                  {"type": "item.set_visible", "scene_id": sid, "item_id": ch, "visible": slot == start}]
        for slot, sname, _ in SLOTS:
            lanes = [{"target": {"channel": channel(screen, other)},
                      "points": [{"at_ms": FADE_MS, "value": 1.0 if other == slot else 0.0,
                                  "curve": "linear"}]} for other, _, _ in SLOTS]
            # On the subscene: a scene holds at most 32 timelines, and the cockpit's
            # views and sequences take most of its.
            e.append({"type": "timeline.set", "scene_id": sid, "timeline": {
                "timeline_id": sequence(screen, slot), "name": f"{name}: {sname}",
                "duration_ms": FADE_MS, "lanes": lanes,
                "cues": _shows(sid, [(channel(screen, o), o == slot) for o, _, _ in SLOTS])}})
        for (slot, _, _), chord in zip(SLOTS, chords):
            keys.append({"type": "hotkey.set", "chord": "Ctrl+Alt+Shift+" + chord,
                         "action": action(screen, slot)})
        e.append({"type": "item.set_source", "item_id": shown_on, "source_id": sid})
    # The key lights: the strip of unlit keys, and a lit block a key over it.
    x, y, w, h = softkeys.KEY_STRIP
    e += [{"type": "source.create", "source_id": "key_unlit", "name": "Soft keys, unlit",
           "kind": {"type": "builtin", "kind": "color"},
           "settings": {"color": KEY_UNLIT, "width": 64, "height": 16}},
          {"type": "source.create", "source_id": "key_lit", "name": "Soft key, lit",
           "kind": {"type": "builtin", "kind": "color"},
           "settings": {"color": KEY_LIT, "width": 32, "height": 16}},
          {"type": "item.add", "scene_id": "atlas", "item_id": "keys_unlit", "source_id": "key_unlit",
           "geometry": {"center": {"x": x + w / 2, "y": y + h / 2}, "size": {"width": w, "height": h},
                        "fit_mode": "stretch"}}]
    if unlit_gates:
        e.append({"type": "item.set_motion", "scene_id": "atlas", "item_id": "keys_unlit",
                  "motion": list(unlit_gates)})
    for n, (screen_name, i, *_) in enumerate(softkeys.keys()):
        screen = screen_name.replace("screen_", "").replace("hologram", "holo")
        if screen == "holo" and not hologram:
            continue
        ch = channel(screen, SLOTS[i][0])
        sx, sy, sw, sh = softkeys.slot(n)
        e += [{"type": "item.add", "scene_id": "atlas", "item_id": "key_" + ch[4:], "source_id": "key_lit",
               "geometry": {"center": {"x": sx + sw / 2, "y": sy + sh / 2},
                            "size": {"width": sw, "height": sh}, "fit_mode": "stretch"}},
              {"type": "item.set_motion", "scene_id": "atlas", "item_id": "key_" + ch[4:],
               "motion": [_follow(ch)] + list(gates)}]
    return e + keys


FOLDER = "monitor_sources"
FOLDER_NAME = "Monitor sources"


def filing(hologram=True):
    """The edits that make the scene list's `Monitor sources` folder and file every
    subscene in it. Separate, since a JStream before scene folders has none."""
    ids = [s for s, *_ in SCREENS if hologram or s != "holo"] + ["desk"]
    return ([{"type": "folder.create", "folder_id": FOLDER, "name": FOLDER_NAME}]
            + [{"type": "scene.set_folder", "scene_id": "src_" + s, "folder_id": FOLDER} for s in ids])


# ---- the desk's grid controller: its pads and meter bridge, or a camera ----
# The desk is the atlas's 960 x 360 (8:3) cell at 0, 720 (build_daw.py: the pads, the
# meter bridge and their unlit pages under them). Its subscene, `src_desk`, draws each slot
# in the canvas's middle 8:3 (1920 x 720), and one atlas item, `a_desk`, fills the cell
# from the 16:9 subscene, so nothing is stretched. A long camera picture, such as one
# looking down on a grid controller, fits the cell's 8:3 well.
DESK = (0, 720, 960, 360)
DESK_H = W * 3 / 8
# (slot, its name, its key after Ctrl+Alt+Shift)
DESK_SLOTS = [("grid", "Pads and meters", "KeyN"), ("feed", "Camera feed", "KeyK")]


def desk_controls():
    """What a person plays for the desk, in note order: [(name, key chord, action)]."""
    return [(f"Desk: {name}", "Ctrl+Alt+Shift+" + key, action("desk", slot)) for slot, name, key in DESK_SLOTS]


def desk_edits(layers):
    """The desk's subscene. `layers` are the atlas items on the desk's cell, bottom up:
    (item, source, x, y, w, h, motion), which the subscene's `grid` slot draws at the same
    places (each keeping its motion, the lights' switches on the unlit pads) and the
    atlas gives up for `a_desk`. The `feed` slot is a camera, `desk_feed`, a stand-in still
    until a person points it at a camera."""
    sid = "src_desk"
    dx, dy, dw, dh = DESK
    sx, sy = W / dw, DESK_H / dh
    top = (H - DESK_H) / 2
    e = [{"type": "source.create", "source_id": "desk_feed",
          "name": "Desk camera feed (swap for a camera, such as one over a controller)",
          "kind": {"type": "builtin", "kind": "image"}, "settings": {"file": asset(STANDIN)}},
         {"type": "scene.create", "scene_id": sid, "name": "Desk source"},
         {"type": "source.create", "source_id": sid, "name": "Desk source",
          "kind": {"type": "scene", "scene_id": sid}, "settings": {}}]
    members = {}
    for slot, name, _ in DESK_SLOTS:
        ch = channel("desk", slot)
        e.append({"type": "channel.set", "channel": {
            "channel_id": ch, "name": f"Desk: {name}", "default": 1.0 if slot == "grid" else 0.0}})
        if slot == "feed":
            placed = [(ch, "desk_feed", dx, dy, dw, dh, [], "fill")]
        else:
            placed = [(f"{ch}_{item[2:]}", source, x, y, w, h, motion, "stretch")
                      for item, source, x, y, w, h, motion in layers]
        members[slot] = [p[0] for p in placed]
        for item, source, x, y, w, h, motion, fit in placed:
            e += [{"type": "item.add", "scene_id": sid, "item_id": item, "source_id": source,
                   "geometry": {"center": {"x": (x - dx + w / 2) * sx, "y": top + (y - dy + h / 2) * sy},
                                "size": {"width": w * sx, "height": h * sy}, "fit_mode": fit}},
                  {"type": "item.set_visible", "scene_id": sid, "item_id": item,
                   "visible": slot == "grid"}]
            if motion:
                e.append({"type": "item.set_motion", "scene_id": sid, "item_id": item,
                          "motion": list(motion)})
    for slot, name, key in DESK_SLOTS:
        lanes = [{"target": {"channel": channel("desk", other)},
                  "points": [{"at_ms": FADE_MS, "value": 1.0 if other == slot else 0.0, "curve": "linear"}]}
                 for other, _, _ in DESK_SLOTS]
        e += [{"type": "timeline.set", "scene_id": sid, "timeline": {
                  "timeline_id": sequence("desk", slot), "name": f"Desk: {name}",
                  "duration_ms": FADE_MS, "lanes": lanes,
                  "cues": _shows(sid, [(i, o == slot) for o, _, _ in DESK_SLOTS for i in members[o]])}},
              {"type": "hotkey.set", "chord": "Ctrl+Alt+Shift+" + key, "action": action("desk", slot)}]
    e += [{"type": "item.remove", "item_id": item} for item, *_ in layers]
    # Under the screens' covers, so the desk's monitor switch still blacks it.
    e += [{"type": "item.add", "scene_id": "atlas", "item_id": "a_desk", "source_id": sid,
           "geometry": {"center": {"x": dx + dw / 2, "y": dy + dh / 2}, "size": {"width": dw, "height": dh},
                        "fit_mode": "fill"}},
          {"type": "item.reorder", "item_id": "a_desk", "index": 1}]
    return e
