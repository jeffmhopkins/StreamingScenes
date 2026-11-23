"""Imports the whole DAW cockpit show into a running JStream (the desktop app started with
`--mcp`, or the daemon) over MCP, in one go, into a new project of its own:

- the 3D DAW cockpit (build_daw.py): the model, its screens atlas, the sky, the lights,
  the reflections, the filters, and the data modifiers that move them with Bitwig;
- the camera views (views.py) as keyframes of the cockpit scene, a glide between them,
  and a hotkey for each: Ctrl+Alt+1 to 9, 0, - and =;
- the hologram (hologram.py), a display that projects up from the dash: Ctrl+Alt+H
  shows or hides it, Ctrl+Alt+Shift+H hides it, and its `holo_feed` source is the one to swap
  for a camera or a screen capture;
- two 2D scenes beside it, "DAW desk 2D" and "Be right back", from the same live data;
- hotkeys for the scenes: Ctrl+Alt+F1 the cockpit, F2 the 2D desk, F3 be right back;
- with NOTES=1, Bitwig MIDI notes on channel 16 that switch the views too (below);
- and the studio keeps the scenes warm, so switching between 2D and 3D starts nothing.

    python3 import_show.py [project file]

The project file is where the new project is saved, a new file (default: `DAW
show.json` beside this folder's parent, numbered if it exists). Nothing else is needed:
no page server and no copies, since the screens' pages go in inline and the model is
read from this checkout. JS_TOKEN and JS_MCP are as for ../jstream/mcp.py; build_daw.py's
variables tune the cockpit.

Bitwig's state reaches the scene once the app receives from the JTunnel sender named
`Bitwig` (the app's own setting, "Receive from JTunnel senders", which only a person
changes). With NOTES=1, a JTunnel plugin on a Bitwig track that sends MIDI switches the
views with notes 36 (C1) up on channel 16, in VIEWS order, once the app accepts that
plugin's sender too: an accepted sender's MIDI reaches the bindings.
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

import mcp  # noqa: E402
from mcp import batch, init, op  # noqa: E402

GLIDE_MS = int(os.environ.get("GLIDE_MS", "1800"))
FADE_MS = int(os.environ.get("FADE_MS", "600"))
NOTES = os.environ.get("NOTES", "0") == "1"
NOTE_CHANNEL = int(os.environ.get("NOTE_CHANNEL", "16"))
WARM = int(os.environ.get("WARM", "3"))


def must(result, what):
    text, ok = result
    if not ok:
        sys.exit(f"{what} failed: {text[:400]}")
    return text


def project_path():
    if len(sys.argv) > 1:
        return os.path.abspath(sys.argv[1])
    base = os.path.abspath(os.path.join(HERE, "..", "DAW show"))
    path, n = base + ".json", 2
    while os.path.exists(path):
        path, n = f"{base} {n}.json", n + 1
    return path


# ---- a new project, so a fresh app (or one with other work open) starts clean ----
init()
PROJECT = project_path()
text, ok = op({"type": "collection.new", "path": PROJECT})
if not ok:
    sys.exit(f"couldn't start a new project at {PROJECT}: {text[:400]}\n"
             "Give another path: python3 import_show.py <new file>")
print("new project", PROJECT)
mcp._close()
mcp.S["sid"] = None

# ---- the 3D cockpit ----
runpy.run_path(os.path.join(HERE, "build_daw.py"), run_name="__main__")
mcp._close()
mcp.S["sid"] = None
init()

from views import SHOTS, VIEWS  # noqa: E402

# ---- the camera views: keyframes of the cockpit, glided between ----
must(op({"type": "transition.create", "preset_id": "glide", "name": f"Glide {GLIDE_MS} ms",
         "kind": "move", "duration_ms": GLIDE_MS, "easing": "ease_in_out"}), "glide")
must(op({"type": "transition.create", "preset_id": "fade", "name": f"Fade {FADE_MS} ms",
         "kind": "fade", "duration_ms": FADE_MS, "easing": "ease_in_out"}), "fade")
edits = []
for shot, name, _ in VIEWS:
    if shot == "cockpit":
        edits.append({"type": "scene.set_camera", "scene_id": "cockpit", "camera": SHOTS[shot]})
        continue
    edits += [{"type": "scene.create_variant", "scene_id": "view_" + shot, "variant_of": "cockpit",
               "name": f"Cockpit · {name}"},
              {"type": "scene.set_camera", "scene_id": "view_" + shot, "camera": SHOTS[shot]}]
must(batch(edits, "views"), "views")


def view_scene(shot):
    return "cockpit" if shot == "cockpit" else "view_" + shot


# ---- the hologram (hologram.py): projects up from the dash on Ctrl+Alt+H (again: away), away on
# Ctrl+Alt+Shift+H; every view's camera draws in stacking order so it shows ----
import hologram  # noqa: E402

hologram.add("cockpit", {view_scene(shot): SHOTS[shot] for shot, _, _ in VIEWS})


# ---- two 2D scenes from the same live data ----
def src(sid, name, kind, settings):
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": kind}, "settings": settings}


def add(scene, item, source, cx, cy, w, h, **kw):
    # Item IDs are the collection's, not the scene's: each is the scene's and the item's.
    e = {"type": "item.add", "scene_id": scene, "item_id": f"{scene}_{item}", "source_id": source,
         "geometry": {"center": {"x": cx, "y": cy}, "size": {"width": w, "height": h}}}
    e.update(kw)
    return e


TITLE = os.environ.get("TITLE", "LIVE FROM THE STUDIO")
must(batch([
    src("bg_2d", "2D background", "color", {"color": "#070b12ff", "width": 1920, "height": 1080}),
    src("title_2d", "2D title", "text", {"text": TITLE, "size": 54, "face": "condensed_bold",
                                          "color": "#ffb040ff"}),
    src("brb_2d", "Be right back", "text", {"text": "BE RIGHT BACK", "size": 120,
                                             "face": "condensed_bold", "color": "#ffffffff"}),
    {"type": "scene.create", "scene_id": "desk_2d", "name": "DAW desk 2D"},
    add("desk_2d", "bg", "bg_2d", 960, 540, 1920, 1080),
    add("desk_2d", "title", "title_2d", 960, 70, 1200, 80, fit_mode="fit"),
    # The launcher and the meters as the desk shows them, big, with the pages around.
    add("desk_2d", "launcher", "launcher", 520, 560, 800, 480),
    add("desk_2d", "meters", "meters", 1080, 560, 290, 480, fit_mode="stretch"),
    add("desk_2d", "master", "master", 1270, 560, 56, 480, fit_mode="stretch"),
    add("desk_2d", "transport", "p_transport", 1620, 330, 480, 270, fit_mode="stretch"),
    add("desk_2d", "mixer", "p_mixer", 1620, 640, 480, 270, fit_mode="stretch"),
    add("desk_2d", "arrange", "p_arrange", 960, 960, 1760, 180, fit_mode="fill"),
    {"type": "scene.create", "scene_id": "brb_2d", "name": "Be right back"},
    add("brb_2d", "bg", "bg_2d", 960, 540, 1920, 1080),
    add("brb_2d", "brb", "brb_2d", 960, 420, 1400, 160, fit_mode="fit"),
    add("brb_2d", "transport", "p_transport", 960, 760, 640, 360, fit_mode="stretch"),
], "2d scenes"), "2d scenes")

# ---- hotkeys: the views glide, the scenes fade ----
keys = []
for shot, _, key in VIEWS:
    keys.append({"type": "hotkey.set", "chord": "Ctrl+Alt+" + key,
                 "action": {"type": "scene.switch", "scene_id": view_scene(shot), "preset_id": "glide"}})
for key, scene in [("F1", "cockpit"), ("F2", "desk_2d"), ("F3", "brb_2d")]:
    keys.append({"type": "hotkey.set", "chord": "Ctrl+Alt+" + key,
                 "action": {"type": "scene.switch", "scene_id": scene, "preset_id": "fade"}})
must(batch(keys, "hotkeys"), "hotkeys")

if NOTES:
    notes = [{"type": "binding.set",
              "trigger": {"kind": "midi_note", "note": 36 + i, "channel": NOTE_CHANNEL},
              "action": {"type": "scene.switch", "scene_id": view_scene(shot), "preset_id": "glide"}}
             for i, (shot, _, _) in enumerate(VIEWS)]
    must(batch(notes, "notes"), "notes")

# ---- the screens atlas is a picture for the model, not a scene to show: a group, out of
# the scene list, and last, since opening the project puts its first scene on program ----
must(batch([{"type": "scene.set_role", "scene_id": "atlas", "role": "group"},
            {"type": "scene.reorder", "scene_id": "atlas", "index": len(VIEWS) + 2}], "atlas"), "atlas")

# ---- keep the scenes warm, and start on the wide view ----
text, ok = op({"type": "studio.set_warm", "scenes": WARM})
if not ok:
    print("couldn't set the warm scenes:", text[:200], file=sys.stderr)
must(op({"type": "scene.switch", "scene_id": "cockpit"}), "switch")
print("imported: views Ctrl+Alt+1..0, -, =; scenes Ctrl+Alt+F1 3D, F2 2D desk, F3 be right back;"
      " hologram Ctrl+Alt+H on or off, Ctrl+Alt+Shift+H off")
print("saved to", PROJECT)
