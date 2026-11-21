"""Puts a shot on program with a cut and saves a snapshot: python3 snap_shot.py <variant> <out.png>."""
import sys, time
from mcp import init, op, snap
init()
op({"type": "scene.switch", "scene_id": sys.argv[1], "preset_id": None} if False else {"type": "scene.switch", "scene_id": sys.argv[1]})
time.sleep(float(sys.argv[3]) if len(sys.argv) > 3 else 4)
t = time.time()
print("snap", snap(sys.argv[2]), round(time.time() - t, 2), "s")
