"""What the cockpit's three main monitors and its hologram show, each switchable: every one
shows a subscene of its own (a group scene placed as a source), and the subscene holds one
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
device, and the hologram on its feed, as before. A person changes what a slot shows by
pointing its item (`src_<screen>_<slot>`, in the subscene) at another source, in the app
or with `item.set_source`; the key and its sequence still pick it.

Each slot is a channel, `src_<screen>_<slot>` (1 shown, 0 not), that its item's opacity
and its key's light follow. A sequence a slot, `<screen>_<slot>` ("Centre monitor:
Mixer"), takes its screen's five channels to that slot in FADE_MS (150), from wherever
they are, so a second press mid-fade glides on. Play one from the app's sequences, a
hotkey (KEYS: Ctrl+Alt+Shift with 1 to 5 for the left monitor, 6 to 0 the centre, Y to
P the right and Z to B the hologram), a MIDI note (import_show.py's NOTES), a show cue or
an agent's `timeline.play`.

The keys' lights are the model's `softkey_lights` (cockpit-3d/tools/softkeys.py): a quad
on each key's face maps one block of the screens atlas's key strip, so a lit block in the
atlas lights its key. The atlas holds a dim strip of unlit keys there and, over it, a lit
block per key, which follows the key's slot channel, the glow switch and the master: the
keys are LEDs, so the Glow and Master switches darken them as they do the others.

Everything here is generic JStream: group scenes as sources, channels, sequences with
lanes, hotkeys and `channel` motion modifiers.
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


def edits(hologram=True, gates=()):
    """The subscenes, their channels and sequences, the hotkeys, the key lights in the
    `atlas` scene, and the screens pointed at the subscenes. `gates` are more motion
    modifiers for every lit key (build_daw.py's glow and master switches)."""
    e = [{"type": "source.create", "source_id": "feed",
          "name": "Monitor camera feed (swap for a camera or capture)",
          "kind": {"type": "builtin", "kind": "image"},
          "settings": {"file": asset(STANDIN)}}]
    keys = []
    for screen, name, shown_on, start, chords in SCREENS:
        if screen == "holo" and not hologram:
            continue
        sid = "src_" + screen
        e += [{"type": "scene.create", "scene_id": sid, "name": f"{name} source", "role": "group"},
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
                  {"type": "item.set_motion", "scene_id": sid, "item_id": ch, "motion": [_follow(ch)]}]
        for slot, sname, _ in SLOTS:
            lanes = [{"target": {"channel": channel(screen, other)},
                      "points": [{"at_ms": FADE_MS, "value": 1.0 if other == slot else 0.0,
                                  "curve": "linear"}]} for other, _, _ in SLOTS]
            # On the subscene: a scene holds at most 32 timelines, and the cockpit's
            # views and sequences take most of its.
            e.append({"type": "timeline.set", "scene_id": sid, "timeline": {
                "timeline_id": sequence(screen, slot), "name": f"{name}: {sname}",
                "duration_ms": FADE_MS, "lanes": lanes}})
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
