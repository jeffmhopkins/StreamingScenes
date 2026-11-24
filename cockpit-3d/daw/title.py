"""The Sound Journal title: whatever is on program darkened, with the JMH shield and
"Sound Journal" over it, faded in and out by a key, as Jeff's OBS overlay did.

    python3 title.py add      # into a running JStream that has build_daw.py's cockpit
    python3 title.py on       # fade it in
    python3 title.py off      # fade it out

The title is an overlay (JStream ADR-0210 decision 11): a 2D scene, `sound_journal`
("Sound Journal"), put over program, so the view on program stays where it is, whichever
keyframe of the cockpit it is. The scene is a black card over the whole canvas, which
darkens what is under it, and the title card (`title/title.png`, which
`title/make_title.py` draws). An overlay can't blur what is under it, so the title no
longer blurs the cockpit as it did when it nested it.

Ctrl+Alt+J puts it up (`overlay.show`) and Ctrl+Alt+Shift+J takes it down
(`overlay.hide`), each through the overlay's fade; import_show.py puts the same on notes
`TITLE_NOTE` (84, C6) and 85. A sequence's cue can't put an overlay up, so the title no
longer has a channel, and CC 45 and Mod 20 no longer drive it. Neither key touches
program.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from mcp import asset, batch, init, op  # noqa: E402

SCENE = "sound_journal"
CARD = os.path.join(HERE, "title", "title.png")
TITLE_NOTE = int(os.environ.get("TITLE_NOTE", "84"))   # on; off is the next note up
TITLE_DIM = float(os.environ.get("TITLE_DIM", "0.62"))
KEY_ON, KEY_OFF = "Ctrl+Alt+KeyJ", "Ctrl+Alt+Shift+KeyJ"
CARD_W, CARD_H, CARD_Y = 800, 600, 580   # the card (1200 x 900 drawn) on the 1920 x 1080 canvas


ON = {"type": "overlay.show", "scene_id": SCENE}
OFF = {"type": "overlay.hide", "scene_id": SCENE}
# What a person plays: (its name, the key after Ctrl+Alt, the action), as ship_sequences.CONTROLS.
CONTROLS = [("Sound Journal title on", "KeyJ", ON), ("Sound Journal title off", "Shift+KeyJ", OFF)]


def edits():
    """Everything this adds, as one batch: the scene and the keys."""
    full = {"center": {"x": 960, "y": 540}, "size": {"width": 1920, "height": 1080}}
    card = {"center": {"x": 960, "y": CARD_Y}, "size": {"width": CARD_W, "height": CARD_H}}
    return [
        {"type": "source.create", "source_id": "sj_black", "name": "Sound Journal dim",
         "kind": {"type": "builtin", "kind": "color"},
         "settings": {"color": "#000000ff", "width": 1920, "height": 1080}},
        {"type": "source.create", "source_id": "sj_card", "name": "Sound Journal title",
         "kind": {"type": "builtin", "kind": "image"}, "settings": {"file": asset(CARD)}},
        {"type": "scene.create", "scene_id": SCENE, "name": "Sound Journal"},
        {"type": "item.add", "scene_id": SCENE, "item_id": "sj_dim", "source_id": "sj_black",
         "geometry": full, "opacity": TITLE_DIM},
        {"type": "item.add", "scene_id": SCENE, "item_id": "sj_title", "source_id": "sj_card",
         "geometry": card},
    ] + [{"type": "hotkey.set", "chord": "Ctrl+Alt+" + key, "action": action}
         for _, key, action in CONTROLS]


def add():
    text, ok = batch(edits(), "sound journal title")
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
