"""Plays the cockpit timeline (tools/rec.js) on the JStream scene and records it.

Each event switches the program to a keyframe variant, as a hotkey would. The hologram
fades and the key label are stepped from here. With SLOW=F the pages' clock runs F times
slower (slowserve.py) and every time here is stretched by F, so a machine that composites
under real time still records every moment; the recording is then retimed by 1/F.
"""
import os, sys, time, json
from mcp import *

F = float(os.environ.get("SLOW", "1"))
END = float(os.environ.get("END", "55500"))
OUT = os.path.abspath(os.environ.get("OUT", "cockpit-slow.mp4"))

EV = [
    (0, "F1", "Cruise: deep space", "cruise_deep"),
    (3000, "F6", "Monitors: radar and audio", "scan_deep"),
    (6500, "F2", "Warp to the Kestrel Nebula", "warp_deep"),
    (11000, "F3", "Arrive: Kestrel Nebula", "arrive_nebula"),
    (15000, "F7", "Monitors: navigation", "nav_nebula"),
    (17000, "F8", "Weapons: destroy target", "weapons_nebula"),
    (25000, "F4", "Taking fire", "hit_nebula"),
    (30500, "F2", "Warp to Tyr VII", "warp_nebula"),
    (35000, "F3", "Arrive: Tyr VII", "arrive_planet"),
    (39000, "F5", "Incoming transmission", "tx_planet"),
    (47000, "F9", "Bitwig hologram", "bitwig_planet"),
]


def cl(v):
    return max(0.0, min(1.0, v))


def key_opacity(d):
    return 0 if d < 0 else d / 150 if d < 150 else 1 if d < 1800 else cl(1 - (d - 1800) / 300)


init()
op({"type": "scene.switch", "scene_id": "cruise_deep"})
time.sleep(3)
op({"type": "output.delete", "output_id": "rec"})
op({"type": "output.create", "output_id": "rec",
    "kind": {"type": "record", "path": OUT, "container": "mp4"}})
op({"type": "output.set_encoder", "output_id": "rec", "profile_id": "hq"})
sent = {}


def opacity(scene, item, v):
    k = (scene, item)
    v = round(v, 3)
    if sent.get(k) is None or abs(sent[k] - v) >= 0.02 or (v in (0, 0.75, 0.85, 1) and sent[k] != v):
        e = {"type": "item.set_opacity", "item_id": item, "opacity": v}
        if scene:
            e["scene_id"] = scene
        op(e)
        sent[k] = v


_, ok_ = op({"type": "output.start", "output_id": "rec"})
if not ok_:
    sys.exit(1)
t0 = time.time()
nxt = 0
key_at = -1e9
cur = "cruise_deep"
switched = {}
log = []
while True:
    s = (time.time() - t0) * 1000 / F  # scene time, ms
    if s > END:
        break
    while nxt < len(EV) and s >= EV[nxt][0]:
        at, k, label, vid = EV[nxt]
        if vid == "bitwig_planet":
            opacity("bitwig_planet", "caller", sent.get(("tx_planet", "caller"), 0.75))
        if at:
            op({"type": "source.set_settings", "source_id": "key",
                "patch": {"text": f"{k}  {label}"}})
            op({"type": "scene.switch", "scene_id": vid})
        else:
            op({"type": "source.set_settings", "source_id": "key",
                "patch": {"text": f"{k}  {label}"}})
        log.append((round(time.time() - t0, 2), round(s), vid))
        print("event", log[-1], flush=True)
        key_at = at
        cur = vid
        switched[vid] = at
        nxt += 1
    opacity(None, "key", key_opacity(s - key_at))
    if "tx_planet" in switched and cur == "tx_planet":
        opacity("tx_planet", "caller", 0.75 * cl((s - switched["tx_planet"] - 1700) / 400))
    if cur == "bitwig_planet":
        d = s - switched["bitwig_planet"]
        opacity("bitwig_planet", "caller", 0.75 * cl(1 - d / 250))
        opacity("bitwig_planet", "daw", 0.85 * cl((d - 1100) / 500))
    time.sleep(min(0.5, max(0.02, F * 0.01)))
op({"type": "output.stop", "output_id": "rec"})
json.dump({"F": F, "events": log, "real_s": time.time() - t0}, open(OUT + ".json", "w"))
print("done", time.time() - t0)
