"""The demo's shot list, shared by drive.py (a live recording) and render_frames.py
(frame by frame on the held clock)."""
import os

# (scene time in ms, variant, glide preset, the sky's warp or None)
EVENTS = [
    (0, "cockpit", None, None),
    (2500, "seat", "glide_long", None),      # into the pilot's seat, the monitor in focus
    (9000, "window", "glide", None),         # look up and out: focus pulls to the planet
    (15500, "warp", "glide_short", 0.85),    # cabin lights out, and jump to warp
    (23000, "seat", "glide", 0.0),           # drop out of warp, lights back up
    (28000, "monitor", "glide_long", None),  # down and close on the live monitor
    (35000, "cockpit", "glide_long", None),  # back out behind the pilot
]
END = float(os.environ.get("END", "41500"))
