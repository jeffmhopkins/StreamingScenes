"""Builds the inputs of jstream-demos.json, the one JStream project that holds the feature
tour and the DAW cockpit, with three shows: Feature tour, Cockpit tour and Lightning tour.

    python3 tools/build_demos.py

writes, in build/ (not committed):

- tour.json: the feature tour's scenes and shows, from feature-tour/tools/make_tour.py;
- cockpit-edits.json: every edit cockpit-3d/daw/import_show.py sends a running JStream,
  recorded by running it against a stand-in MCP client that takes every edit. The edits
  name files by their path from the repo's root, so the project finds them from the
  root. The cockpit's view keys move from Ctrl+Alt+digit to Ctrl+Shift+digit (and - and
  =), since the tour's Go to keys hold Ctrl+Alt+1 to 8 and 0; the tour's title lower third
  moves to Ctrl+Alt+T, since the cockpit's lights-on key is Ctrl+Alt+L. The cockpit is
  recorded with CC=1 and NOTES=1, so every Bitwig input it has is mapped; the tour's MIDI
  pads (notes 36 to 39) listen on channel 1, so they don't answer the cockpit's notes on
  channel 16.

Then tools/bake_demos.rs applies the edits to the tour with JStream's own collection code
and saves the project in the canonical form JStream writes; see that file.
"""
import json
import os
import runpy
import subprocess
import sys
import types

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
BUILD = os.path.join(ROOT, "build")
DAW = os.path.join(ROOT, "cockpit-3d", "daw")
os.makedirs(BUILD, exist_ok=True)

subprocess.run([sys.executable, os.path.join(ROOT, "feature-tour", "tools", "make_tour.py"),
                os.path.join(BUILD, "tour.json")], check=True)

# ---- the cockpit, recorded, with every Bitwig input import_show.py offers: the camera
# CCs 20 to 29 (CC=1, which also gives each view its depth of field and autofocus) and the
# notes that switch the views and play the sequences (NOTES=1), all on channel 16, beside
# the light switches, the ship's CCs, the JTunnel Mods and the data it always maps ----
os.environ.setdefault("CC", "1")
os.environ.setdefault("NOTES", "1")
RECORDED = []
mcp = types.ModuleType("mcp")
mcp.S, mcp.W, mcp.H = {"sid": None, "id": 0}, 1920, 1080


def _op(o, **kw):
    RECORDED.append(o)
    return "recorded", True


def _batch(edits, label=""):
    RECORDED.extend(edits)
    return "recorded", True


def _geo(x, y, w, h, **kw):
    g = {"center": {"x": x + w / 2, "y": y + h / 2}, "size": {"width": w, "height": h}}
    g.update(kw)
    return g


def _refuse(*a, **kw):
    raise RuntimeError("the recorder answers only op and batch")


mcp.op, mcp.batch, mcp.geo = _op, _batch, _geo
mcp.asset = lambda path: {"type": "asset", "root": "absolute", "path": path}
mcp.init = mcp._close = lambda: None
mcp.call = mcp.post = mcp.snap = _refuse
sys.modules["mcp"] = mcp
here = os.getcwd()
os.chdir(DAW)
sys.path.insert(0, DAW)
argv = sys.argv
sys.argv = ["import_show.py", os.path.join(BUILD, "unused.json")]
runpy.run_path(os.path.join(DAW, "import_show.py"), run_name="__main__")
sys.argv = argv
os.chdir(here)

# What a running app does and a project file doesn't hold, and the fade the tour has already.
SKIP = {"collection.new", "scene.switch", "studio.set_warm", "canvas.set_size", "scene.reorder"}
MOVE_KEYS = {f"Ctrl+Alt+Digit{d}" for d in range(10)} | {"Ctrl+Alt+Minus", "Ctrl+Alt+Equal"}


def relative(value):
    if isinstance(value, dict):
        if value.get("type") == "asset" and value.get("root") == "absolute":
            path = os.path.relpath(value["path"], ROOT).replace(os.sep, "/")
            assert not path.startswith(".."), value["path"]
            return {"type": "asset", "root": "collection", "path": path}
        return {k: relative(v) for k, v in value.items()}
    if isinstance(value, list):
        return [relative(v) for v in value]
    return value


edits = []
for e in RECORDED:
    if e["type"] in SKIP or (e["type"] == "transition.create" and e.get("preset_id") == "fade"):
        continue
    if e["type"] == "hotkey.set" and e["chord"] in MOVE_KEYS:
        e = dict(e, chord=e["chord"].replace("Ctrl+Alt+", "Ctrl+Shift+"))
    edits.append(relative(e))
with open(os.path.join(BUILD, "cockpit-edits.json"), "w") as f:
    json.dump(edits, f)
print(f"build/tour.json and build/cockpit-edits.json ({len(edits)} edits); now bake them with "
      "tools/bake_demos.rs")
