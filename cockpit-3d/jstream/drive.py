"""Plays the demo's shot list on the cockpit scene and records the program.

Each event switches the program to a keyframe variant with a glide preset, as a hotkey
would. Build the scene with the same SLOW=F first (build_scene.py stretches the glides
and the feed's motion F times); every time here is stretched by F too, so a machine that
composites under real time still records every moment. Retime the recording by 1/F:

    ffmpeg -i cockpit-slow.mp4 -vf "setpts=(PTS-STARTPTS)/F,fps=30" -an cockpit-demo.mp4
"""
import json
import os
import sys
import time

from mcp import init, op

F = float(os.environ.get("SLOW", "1"))
OUT = os.path.abspath(os.environ.get("OUT", "cockpit-slow.mp4"))

from drive_events import END, EVENTS

init()
op({"type": "scene.switch", "scene_id": "cockpit"})
time.sleep(3)
op({"type": "encoder.create", "profile_id": "hq", "name": "Recording, high quality",
    "profile": {"video": {"codec": "h264", "hardware": "avoid", "keyframe_interval_s": 10,
                          "rate_control": {"type": "vbr", "kbps": 20000, "max_kbps": 40000}},
                "audio": {"codec": "aac", "kbps": 128}}})
op({"type": "output.delete", "output_id": "rec"})
op({"type": "output.create", "output_id": "rec",
    "kind": {"type": "record", "path": OUT, "container": "mp4"}})
op({"type": "output.set_encoder", "output_id": "rec", "profile_id": "hq"})
_, ok = op({"type": "output.start", "output_id": "rec"})
if not ok:
    sys.exit("record did not start")
t0 = time.time()
log = []
for at, vid, preset, warp in EVENTS:
    while (time.time() - t0) * 1000 / F < at:
        time.sleep(0.05)
    if at:
        e = {"type": "scene.switch", "scene_id": vid}
        if preset:
            e["preset_id"] = preset
        op(e)
    if warp is not None:
        # The sky ramps itself to the new warp over its warp_ramp_s.
        op({"type": "source.set_settings", "source_id": "l_env", "patch": {"warp": warp}})
    log.append((round(time.time() - t0, 2), at, vid))
    print("event", log[-1], flush=True)
while (time.time() - t0) * 1000 / F < END:
    time.sleep(0.1)
op({"type": "output.stop", "output_id": "rec"})
json.dump({"F": F, "events": log, "real_s": time.time() - t0}, open(OUT + ".json", "w"))
print("done", round(time.time() - t0, 1))
