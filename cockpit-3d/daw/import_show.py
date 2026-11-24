"""Imports the whole DAW cockpit show into a running JStream (the desktop app started with
`--mcp`, or the daemon) over MCP, in one go, into a new project of its own:

- the 3D DAW cockpit (build_daw.py): the model, its screens atlas, the sky, the lights,
  the reflections, the filters, and the data modifiers that move them with Bitwig;
- the camera views (views.py) as sequences of the cockpit scene, each gliding the
  cockpit's camera from wherever it is to the view, and a hotkey for each: Ctrl+Alt+1 to
  9, 0, - and = (a JStream before sequences, protocol 0.170, gets them as keyframes);
- the hologram (hologram.py), a display that projects up from the dash: Ctrl+Alt+H
  shows it, Ctrl+Alt+Shift+H hides it (before sequences, Ctrl+Alt+H shows or hides it), and its `holo_feed` source is the one to swap
  for a camera or a screen capture;
- the Sound Journal title (title.py): the cockpit darkened and slightly blurred under the
  JMH shield and "Sound Journal", faded in by Ctrl+Alt+J and out by Ctrl+Alt+Shift+J;
- two 2D scenes beside it, "DAW desk 2D" and "Be right back", from the same live data;
- hotkeys for the scenes: Ctrl+Alt+F1 the cockpit, F2 the 2D desk, F3 be right back;
- with NOTES=1, Bitwig MIDI notes on channel 16 that switch the views too (below);
- with CC=1, Bitwig CCs 20 to 27 on channel 16 that move, turn, zoom and focus the
  cockpit's camera in every view (CAMERA_CCS below; needs a JStream whose cameras take
  MIDI, JStream #1631), and, where JStream has them (protocol 0.167), CC 28 for roll and
  CC 29 to switch autofocus off; CC=1 turns on the views' depth of field, and autofocus;
- the Cockpit tour, a show that runs through the views, the lights, the monitors, the
  warp, the hologram and the 2D desk, with a script in each bookmark (show_tour.py; needs
  a JStream with shows, protocol 0.177);
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
CC = os.environ.get("CC", "0") == "1"
CC_CHANNEL = int(os.environ.get("CC_CHANNEL", "16"))
CC_FIRST = int(os.environ.get("CC_FIRST", "20"))
CC_INPUT = os.environ.get("CC_INPUT", "Bitwig")
CC_SMOOTHING_MS = int(os.environ.get("CC_SMOOTHING_MS", "50"))
# How the camera follows its view channels: a little smoothing hides the values thread's
# ticks, which aren't in step with the frames.
VIEW_SMOOTHING_MS = int(os.environ.get("VIEW_SMOOTHING_MS", "40"))
# SEQUENCES=0 makes the views keyframes, as before JStream had sequences.
SEQUENCES = os.environ.get("SEQUENCES", "1") == "1"

# The camera's CCs, from CC_FIRST up, in this order: the property and how far the CC's
# top (127) takes it from the view. Each rests at the view (from 0), since a CC reads 0
# until it is first sent. Scene space is 1000 px to the model's metre, x right, y down
# and z toward the viewer; angles are degrees, fov a zoom in when it drops.
CAMERA_CCS = [
    ("position_x", 300),   # 30 cm to the right
    ("position_y", -200),  # 20 cm up
    ("position_z", -300),  # 30 cm forward
    ("pan", 30),           # turn right
    ("tilt", 20),          # look up
    ("fov", -25),          # zoom in
    ("focus", 600),        # focus further away
    ("blur", 16),          # aperture: more depth-of-field blur
    ("roll", 15),          # clockwise
    ("autofocus", -1),     # past its middle: autofocus off, the focus stays put
]
if CC:
    # Every view gets its depth of field (shots.py's DOF) and starts autofocusing.
    os.environ.setdefault("DOF", "1")


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
BUILT = runpy.run_path(os.path.join(HERE, "build_daw.py"), run_name="__main__")
# Whether the cockpit's switches and warp are channels (protocol 0.169) a sequence can move.
CHANNELS = BUILT.get("CHANNELS", False)
mcp._close()
mcp.S["sid"] = None
init()

from views import SHOTS, VIEWS, sequences, view_id  # noqa: E402

# ---- the camera views ----
must(op({"type": "transition.create", "preset_id": "fade", "name": f"Fade {FADE_MS} ms",
         "kind": "fade", "duration_ms": FADE_MS, "easing": "ease_in_out"}), "fade")
VIEW_CHANNELS, VIEW_MOTION, VIEW_TIMELINES = sequences(GLIDE_MS, VIEW_SMOOTHING_MS)


def sequence_views():
    """The views as sequences: channels for the camera's fields, the cockpit's camera
    following them, and a sequence a view that glides them there. All or nothing, so a
    JStream without sequences (before protocol 0.170) refuses the lot."""
    edits = [{"type": "scene.set_camera", "scene_id": "cockpit", "camera": SHOTS["cockpit"]}]
    edits += [{"type": "channel.set", "channel": ch} for ch in VIEW_CHANNELS]
    edits.append({"type": "scene.set_camera_motion", "scene_id": "cockpit", "motion": VIEW_MOTION})
    edits += [{"type": "timeline.set", "scene_id": "cockpit", "timeline": t} for t in VIEW_TIMELINES]
    text, ok = batch(edits, "view sequences")
    if not ok:
        print("no sequences in this JStream (protocol 0.170): the views are keyframes",
              file=sys.stderr)
    return ok


def keyframe_views():
    """The views as keyframes of the cockpit, each switched to with a glide."""
    must(op({"type": "transition.create", "preset_id": "glide", "name": f"Glide {GLIDE_MS} ms",
             "kind": "move", "duration_ms": GLIDE_MS, "easing": "ease_in_out"}), "glide")
    edits = []
    for shot, name, _ in VIEWS:
        if shot == "cockpit":
            edits.append({"type": "scene.set_camera", "scene_id": "cockpit", "camera": SHOTS[shot]})
            continue
        edits += [{"type": "scene.create_variant", "scene_id": "view_" + shot,
                   "variant_of": "cockpit", "name": f"Cockpit · {name}"},
                  {"type": "scene.set_camera", "scene_id": "view_" + shot, "camera": SHOTS[shot]}]
    must(batch(edits, "views"), "views")


SEQ = SEQUENCES and sequence_views()
if not SEQ:
    keyframe_views()


def view_scene(shot):
    """The scene a view draws through: the cockpit itself with sequences, else its keyframe."""
    return "cockpit" if SEQ or shot == "cockpit" else "view_" + shot


def view_action(shot):
    """What a view's hotkey or note runs."""
    if SEQ:
        return {"type": "timeline.play", "timeline_id": view_id(shot)}
    return {"type": "scene.switch", "scene_id": view_scene(shot), "preset_id": "glide"}


# One camera a scene that draws a view: with sequences, the cockpit's alone.
VIEW_CAMERAS = {view_scene(shot): SHOTS[shot] for shot, _, _ in VIEWS if view_scene(shot) != "cockpit"}
VIEW_CAMERAS["cockpit"] = SHOTS["cockpit"]


# ---- the hologram (hologram.py): projects up from the dash on Ctrl+Alt+H (again: away), away on
# Ctrl+Alt+Shift+H; every view's camera draws in stacking order so it shows ----
import hologram  # noqa: E402

# Its edits go in as one batch, so a JStream without the `hologram` filter (before alpha.8)
# gets none of it, and the rest of the show still imports.
try:
    hologram.add("cockpit", VIEW_CAMERAS, channels=SEQ, holo_inputs=BUILT["mod_inputs"]("holo"))
    HOLOGRAM = True
except SystemExit as e:
    # Most likely a JStream without the `hologram` filter; the reason says which.
    print(f"no hologram ({e}); importing the rest", file=sys.stderr)
    HOLOGRAM = False


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
    keys.append({"type": "hotkey.set", "chord": "Ctrl+Alt+" + key, "action": view_action(shot)})
for key, scene in [("F1", "cockpit"), ("F2", "desk_2d"), ("F3", "brb_2d")]:
    keys.append({"type": "hotkey.set", "chord": "Ctrl+Alt+" + key,
                 "action": {"type": "scene.switch", "scene_id": scene, "preset_id": "fade"}})
must(batch(keys, "hotkeys"), "hotkeys")

# ---- the cockpit's sequences (ship_sequences.py): lights, monitors and warp ----
import ship_sequences  # noqa: E402

SHIP = SEQ and CHANNELS
if SHIP:
    seq = [{"type": "timeline.set", "scene_id": "cockpit", "timeline": t}
           for t in ship_sequences.timelines()]
    seq += [{"type": "hotkey.set", "chord": "Ctrl+Alt+" + key, "action": action}
            for _, key, action in ship_sequences.CONTROLS if key]
    must(batch(seq, "ship sequences"), "ship sequences")

# ---- the Sound Journal title (title.py): the cockpit darkened and blurred under the JMH
# shield and "Sound Journal", faded in on Ctrl+Alt+J and out on Ctrl+Alt+Shift+J ----
import title  # noqa: E402

TITLE = False
if SHIP:
    try:
        title.add("cockpit", [BUILT["cc_input"](title.TITLE_CC, 0.0, 1.0, 50)]
                  + BUILT["mod_inputs"]("title"))
        TITLE = True
    except SystemExit as e:
        print(f"no Sound Journal title ({e}); importing the rest", file=sys.stderr)

if NOTES:
    notes = [{"type": "binding.set",
              "trigger": {"kind": "midi_note", "note": 36 + i, "channel": NOTE_CHANNEL},
              "action": view_action(shot)}
             for i, (shot, _, _) in enumerate(VIEWS)]
    if SHIP:
        # The cockpit's sequences on the notes after the views', from 48 (C2).
        first = 36 + len(VIEWS)
        notes += [{"type": "binding.set",
                   "trigger": {"kind": "midi_note", "note": first + i, "channel": NOTE_CHANNEL},
                   "action": action}
                  for i, (_, _, action) in enumerate(ship_sequences.CONTROLS)
                  if HOLOGRAM or action.get("channel_id") != "holo"]
        # Then the title's on and off.
        first += len(ship_sequences.CONTROLS)
        notes += [{"type": "binding.set",
                   "trigger": {"kind": "midi_note", "note": first + i, "channel": NOTE_CHANNEL},
                   "action": action}
                  for i, (_, _, action) in enumerate(title.CONTROLS if TITLE else [])]
    must(batch(notes, "notes"), "notes")

if CC:
    # Camera motion belongs to the scene's family, so the cockpit's offsets every view
    # alike and carries through a glide between them. With sequences the views' own
    # channels come first in the same list, and the CCs add to wherever they put it.
    motion = [{"modifier_id": "cc_" + prop, "property": prop, "kind": "midi",
               "controller": CC_FIRST + i, "channel": CC_CHANNEL, "input": CC_INPUT,
               "from": 0, "to": to,
               "smoothing_ms": 0 if prop == "autofocus" else CC_SMOOTHING_MS}
              for i, (prop, to) in enumerate(CAMERA_CCS)]
    # Roll and the autofocus switch are the last two: a JStream before protocol 0.167 caps
    # a camera at 8 modifiers and has no autofocus, so it gets the first 8 only.
    base = VIEW_MOTION if SEQ else []
    text, ok = op({"type": "scene.set_camera_motion", "scene_id": "cockpit", "motion": base + motion})
    if ok:
        cams = []
        for sid, view in VIEW_CAMERAS.items():
            # Only a camera with a focus can autofocus (DOF=0 gives none).
            cam = dict(view, autofocus="focus_px" in view)
            cams.append({"type": "scene.set_camera", "scene_id": sid,
                         "camera": hologram.stacking(cam) if HOLOGRAM else cam})
        must(batch(cams, "autofocus"), "autofocus")
        print("camera CCs: 20 to 29, autofocus on")
    else:
        text, ok = op({"type": "scene.set_camera_motion", "scene_id": "cockpit",
                       "motion": base + motion[:8]})
        if ok:
            print("camera CCs: 20 to 27; this JStream has no roll CC or autofocus (before "
                  "protocol 0.167)", file=sys.stderr)
        else:
            print("no camera CCs: this JStream's cameras don't take MIDI (JStream #1631); "
                  "importing the rest", file=sys.stderr)

# ---- the screens atlas is a picture for the model, not a scene to show: a group, out of
# the scene list, and last, since opening the project puts its first scene on program ----
must(batch([{"type": "scene.set_role", "scene_id": "atlas", "role": "group"},
            {"type": "scene.reorder", "scene_id": "atlas",
             "index": (1 if SEQ else len(VIEWS)) + 2 + TITLE}], "atlas"), "atlas")

# ---- the cockpit tour, a show (show_tour.py) that runs through all of it; a JStream
# without shows (before protocol 0.177) imports the rest ----
import show_tour  # noqa: E402

text, ok = batch(show_tour.edits(), "cockpit tour") if SEQ and SHIP else ("needs sequences", False)
TOUR = ok
if not ok:
    print(f"no cockpit tour show ({text[:200]}); importing the rest", file=sys.stderr)

# ---- keep the scenes warm, and start on the wide view ----
text, ok = op({"type": "studio.set_warm", "scenes": WARM})
if not ok:
    print("couldn't set the warm scenes:", text[:200], file=sys.stderr)
must(op({"type": "scene.switch", "scene_id": "cockpit"}), "switch")
print("imported: views Ctrl+Alt+1..0, -, =" + (" (sequences)" if SEQ else " (keyframes)")
      + ("; lights Ctrl+Alt+L on, Shift+L off; monitors M, Shift+M; warp W, Shift+W" if SHIP else "")
      + "; scenes Ctrl+Alt+F1 3D, F2 2D desk, F3 be right back"
      + (("; hologram Ctrl+Alt+H on, Ctrl+Alt+Shift+H off" if SEQ
          else "; hologram Ctrl+Alt+H on or off, Ctrl+Alt+Shift+H off") if HOLOGRAM else "; no hologram")
      + ("; Sound Journal title Ctrl+Alt+J on, Ctrl+Alt+Shift+J off" if TITLE else "")
      + ("; show: Cockpit tour" if TOUR else ""))
print("saved to", PROJECT)
