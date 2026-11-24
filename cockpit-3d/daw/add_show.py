"""Adds the cockpit tour show (show_tour.py) to the DAW show already open in a running
JStream (one import_show.py made), over MCP. import_show.py adds it itself, so this is for
a project imported before the show existed.

    python3 add_show.py

It makes the `tour_tag` scene the show lays over the cockpit, then sets the show; run again,
it sets the show again in place. Save the project afterwards (File › Save, or Ctrl+S).
JS_TOKEN and JS_MCP are as for ../jstream/mcp.py. Needs a JStream with shows (protocol
0.177, JStream ADR-0210).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from mcp import batch, init, op  # noqa: E402

import show_tour  # noqa: E402

init()
text, ok = batch(show_tour.edits(), "cockpit tour")
if not ok:
    # Most likely the tag scene is there from an earlier run: set the show alone.
    text, ok = op({"type": "show.set", "show": show_tour.SHOW})
    if not ok:
        sys.exit(f"couldn't set the show: {text[:400]}")
length = show_tour.LENGTH_MS
print(f"added the show \"{show_tour.SHOW['name']}\": {len(show_tour.SHOW['bookmarks'])} bookmarks, "
      f"{length // 60000}:{length // 1000 % 60:02d}. Save the project to keep it.")
