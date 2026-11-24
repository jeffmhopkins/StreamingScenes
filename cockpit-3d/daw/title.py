"""The Sound Journal title: the cockpit darkened and slightly blurred, with the JMH shield
and "Sound Journal" over it, faded in and out by a switch, as Jeff's OBS overlay did.

    python3 title.py add      # into a running JStream that has build_daw.py's cockpit
    python3 title.py on       # fade it in
    python3 title.py off      # fade it out

JStream draws a 3D scene through its camera, so a fixed overlay goes in a 2D scene that
nests the 3D one (JStream ADR-0094 decision 5). This adds that scene, `sound_journal`
("Sound Journal"): the cockpit, placed over the whole canvas, under the title card
(`title/title.png`, which `title/make_title.py` draws).

Two channels (JStream ADR-0183) drive it:
- `title`, the switch (1 on, 0 off, starting off). Ctrl+Alt+J sets it to 1 and
  Ctrl+Alt+Shift+J to 0; CC `TITLE_CC` (45) on channel 16 from `Bitwig` and the JTunnel
  Mod `TITLE_MOD` (20) are inputs of it, and import_show.py puts it on two MIDI notes.
- `title_fade`, how far in it is (0 to 1): the blur's radius (0 to `TITLE_BLUR_PX`), how
  far the picture darkens (to `1 - TITLE_DIM` of its brightness) and the card's opacity
  all follow it.

The switch rising past one half plays `title_in` (JStream ADR-0184 decision 7): it puts
`sound_journal` on program with a cut, which shows nothing, since the cockpit is drawn
there as it is with `title_fade` at 0, and then fades `title_fade` up over `TITLE_IN_MS`.
Falling past one half plays `title_out`, which fades it down over `TITLE_OUT_MS` and then
cuts back to the cockpit. Each stops the other, so a switch flipped halfway turns round
from where the fade is.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from mcp import asset, batch, init, op  # noqa: E402

SCENE = "sound_journal"
CARD = os.path.join(HERE, "title", "title.png")
TITLE_CC = int(os.environ.get("TITLE_CC", "45"))
TITLE_MOD = int(os.environ.get("TITLE_MOD", "20"))
TITLE_IN_MS = int(os.environ.get("TITLE_IN_MS", "1200"))
TITLE_OUT_MS = int(os.environ.get("TITLE_OUT_MS", "900"))
TITLE_BLUR_PX = float(os.environ.get("TITLE_BLUR_PX", "6"))
TITLE_DIM = float(os.environ.get("TITLE_DIM", "0.62"))
KEY_ON, KEY_OFF = "Ctrl+Alt+KeyJ", "Ctrl+Alt+Shift+KeyJ"
CARD_W, CARD_H, CARD_Y = 800, 600, 580   # the card (1200 x 900 drawn) on the 1920 x 1080 canvas


def _set(value):
    return {"type": "channel.set_value", "channel_id": "title", "value": value}


ON, OFF = _set(1.0), _set(0.0)
# What a person plays: (its name, the key after Ctrl+Alt, the action), as ship_sequences.CONTROLS.
CONTROLS = [("Sound Journal title on", "KeyJ", ON), ("Sound Journal title off", "Shift+KeyJ", OFF)]


def _follow(mid, prop, at1, **kw):
    """`at1` added to `prop` at full fade, nothing at none (unless `from` says otherwise)."""
    m = {"modifier_id": mid, "property": prop, "enabled": True, "clock": "engine", "kind": "channel",
         "channel_id": "title_fade", "smoothing_ms": 0, "curve": "linear", "from": 0.0, "to": at1}
    m.update(kw)
    return m


def _lane(*points):
    return {"target": {"channel": "title_fade"},
            "points": [{"at_ms": at, "value": v, "curve": c} for at, v, c in points]}


def _cut(scene):
    """A cut to `scene`, whatever the scenes' own transitions are."""
    return {"type": "scene.switch", "scene_id": scene, "preset_id": "cut"}


def edits(cockpit="cockpit", inputs=()):
    """Everything this adds, as one batch: the scene, the channels, the sequences and the
    keys. `inputs` are the switch's inputs (its CC and its Mod)."""
    full = {"center": {"x": 960, "y": 540}, "size": {"width": 1920, "height": 1080}}
    card = {"center": {"x": 960, "y": CARD_Y}, "size": {"width": CARD_W, "height": CARD_H}}
    fade_in = {"timeline_id": "title_in", "name": "Sound Journal title in",
               "duration_ms": TITLE_IN_MS,
               "cues": [{"at_ms": 0, "action": _cut(SCENE)}],
               "lanes": [_lane((TITLE_IN_MS, 1.0, "ease_in_out"))],
               "starts": [{"type": "channel", "channel_id": "title", "edge": "rises"}],
               "stops": [{"type": "channel", "channel_id": "title", "edge": "falls"}]}
    fade_out = {"timeline_id": "title_out", "name": "Sound Journal title out",
                "duration_ms": TITLE_OUT_MS,
                "cues": [{"at_ms": TITLE_OUT_MS, "action": _cut(cockpit)}],
                "lanes": [_lane((TITLE_OUT_MS, 0.0, "ease_in_out"))],
                "starts": [{"type": "channel", "channel_id": "title", "edge": "falls"}],
                "stops": [{"type": "channel", "channel_id": "title", "edge": "rises"}]}
    return [
        {"type": "channel.set", "channel": {"channel_id": "title", "name": "Sound Journal title",
                                            "default": 0.0, "inputs": list(inputs)}},
        {"type": "channel.set", "channel": {"channel_id": "title_fade",
                                            "name": "Sound Journal title fade", "default": 0.0}},
        {"type": "source.create", "source_id": "sj_cockpit", "name": "Cockpit (nested)",
         "kind": {"type": "scene", "scene_id": cockpit}, "settings": {}},
        {"type": "source.create", "source_id": "sj_card", "name": "Sound Journal title",
         "kind": {"type": "builtin", "kind": "image"}, "settings": {"file": asset(CARD)}},
        {"type": "scene.create", "scene_id": SCENE, "name": "Sound Journal"},
        {"type": "item.add", "scene_id": SCENE, "item_id": "sj_view", "source_id": "sj_cockpit",
         "geometry": full},
        {"type": "item.add", "scene_id": SCENE, "item_id": "sj_title", "source_id": "sj_card",
         "geometry": card},
        {"type": "filter.add", "owner": {"type": "item", "item_id": "sj_view"}, "chain": "video",
         "filter_id": "sj_blur", "kind": "blur", "settings": {"radius": 0.0}},
        {"type": "filter.add", "owner": {"type": "item", "item_id": "sj_view"}, "chain": "video",
         "filter_id": "sj_dim", "kind": "color_correction", "settings": {"multiply": "#ffffff"}},
        # The blur's radius from 0 and the multiply colour from white toward black (a colour
        # takes a modifier's value as a fraction of full off each of red, green and blue,
        # JStream ADR-0138 decision 3); the card from nothing to opaque.
        {"type": "item.set_motion", "item_id": "sj_view", "motion": [
            _follow("blur", "effect", TITLE_BLUR_PX, effect={"filter_id": "sj_blur", "param": "radius"}),
            _follow("dim", "effect", -TITLE_DIM, effect={"filter_id": "sj_dim", "param": "multiply"})]},
        {"type": "item.set_motion", "item_id": "sj_title",
         "motion": [_follow("fade", "opacity", 0.0, **{"from": -1.0})]},
        {"type": "timeline.set", "scene_id": SCENE, "timeline": fade_in},
        {"type": "timeline.set", "scene_id": SCENE, "timeline": fade_out},
    ] + [{"type": "hotkey.set", "chord": "Ctrl+Alt+" + key, "action": action}
         for _, key, action in CONTROLS]


def add(cockpit="cockpit", inputs=()):
    text, ok = batch(edits(cockpit, inputs), "sound journal title")
    if not ok:
        raise SystemExit(f"the Sound Journal title failed: {text[:400]}")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "add"
    init()
    if what == "add":
        add()
        print("added: Ctrl+Alt+J fades the Sound Journal title in, Ctrl+Alt+Shift+J out")
    elif what in ("on", "off"):
        print(op(ON if what == "on" else OFF)[0][:200])
    else:
        sys.exit(__doc__)
