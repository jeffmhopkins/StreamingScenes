"""The cockpit's sequences (JStream ADR-0184): the lights and the monitors powering on and
off, the jump to warp and back, and the ship's drift. import_show.py adds them, with a
hotkey each, to a cockpit build_daw.py built with channels (ADR-0183).

Each sequence moves channels build_daw.py makes, each one more input of its channel, so
the Bitwig CC on the same channel still works and whichever moved last wins:
- `power_cabin`, `power_desk` and `power_glow`, the light groups' switches (1 on), and
  `power_master`, which every group and the monitors also need on;
- `screen_<cell>`, a monitor's switch (1 on), one per atlas cell;
- `warp`, the sky's warp drive (0 at rest, 1 full);
- `drift_yaw`, `drift_pitch` and `drift_roll`, a small turn of the ship on top of its
  heading, pitch and roll (0.5 none; 0 and 1 are DRIFT_DEG's either way).

The hologram's show and hide are hologram.py's.
"""
import math
import random

# The monitors, in the order they power on: the centre, then outward and up, the desk last.
SCREENS = ["center", "left", "right", "ovl", "ovr", "side_l", "side_r", "desk", "panels"]

LIGHTS_ON_MS, LIGHTS_OFF_MS = 2400, 2600
SCREEN_STEP_MS = 180
WARP_IN_MS, WARP_OUT_MS = 4000, 2500

# The drift: the ship wandering a little on its own, as if adrift, around wherever its
# heading, pitch and roll point it. DRIFT_DEG is how far each channel's 0 and 1 turn it
# either way (build_daw.py maps the channels onto the rig with it); the sequence keeps
# within DRIFT_REACH of that, so the arrival, pinned within 9 degrees of where the warp
# ended, stays in the windshield. One pass is DRIFT_MS, and it loops seamlessly.
DRIFT_DEG = {"yaw": 8.0, "pitch": 5.0, "roll": 6.0}
DRIFT_REACH = 0.9
DRIFT_MS = 450_000
DRIFT_SETTLE_MS = 6000
# Each angle is a sum of slow waves, a whole number of them a pass so the loop has no
# seam: (waves a pass, weight). Their phases are random, from a fixed seed per angle, so
# the three never line up and the drift looks aimless.
DRIFT_WAVES = {"yaw": [(1, 0.7), (3, 1.0), (5, 0.5), (8, 0.25)],
               "pitch": [(2, 0.8), (4, 1.0), (7, 0.4), (9, 0.2)],
               "roll": [(1, 0.5), (4, 1.0), (6, 0.5), (10, 0.2)]}
DRIFT_SEED = {"yaw": 11, "pitch": 23, "roll": 37}


def drift_points(angle, steps=6000):
    """One angle's drift as lane points `(at_ms, value, curve)` over one pass: the wave sum
    at each of its turning points, eased in and out between them, so the ship slows to a
    stop each time it turns, as anything adrift does. The pass starts and ends on a turning
    point (the same one), so the loop's seam is one more turn, and each later pass starts
    from the last point's value, which is the first's."""
    rng = random.Random(DRIFT_SEED[angle])
    waves = [(k, w, rng.uniform(0, 2 * math.pi)) for k, w in DRIFT_WAVES[angle]]

    def f(t):  # t in passes
        return sum(w * math.sin(2 * math.pi * k * t + ph) for k, w, ph in waves)

    ts = [i / steps for i in range(steps)]
    vs = [f(t) for t in ts]
    turns = [i for i in range(steps) if (vs[i] - vs[i - 1]) * (vs[(i + 1) % steps] - vs[i]) <= 0]
    # Start on the turn with the longest way to the next one, so the first glide (from
    # wherever the channel is, at rest the middle) is a slow one.
    gaps = [((turns[(j + 1) % len(turns)] - turns[j]) % steps, turns[j]) for j in range(len(turns))]
    start = max(gaps)[1]
    peak = max(abs(v) for v in vs)
    points = []
    for i in sorted((i - start) % steps for i in turns):
        if i == 0:
            continue
        points.append((round(i * DRIFT_MS / steps), vs[(i + start) % steps], "ease_in_out"))
    points.append((DRIFT_MS, vs[start], "ease_in_out"))
    # A wobble too small to see (two turns close in value, where the waves nearly cancel)
    # would only make the ship pause: drop both of its turns and glide through.
    j = 0
    while j + 2 < len(points):
        if abs(points[j + 1][1] - points[j][1]) < 0.05 * peak:
            del points[j:j + 2]
        else:
            j += 1
    return [(at, round(0.5 + 0.5 * DRIFT_REACH * v / peak, 4), c) for at, v, c in points]


def _lane(channel, *points):
    return {"target": {"channel": channel},
            "points": [{"at_ms": at, "value": v, "curve": c} for at, v, c in points]}


def _timeline(tid, name, duration, lanes):
    return {"timeline_id": tid, "name": name, "duration_ms": duration, "lanes": lanes}


def timelines():
    """Every sequence, as `timeline.set`'s `timeline`."""
    n = len(SCREENS)
    return [
        # Lights on: the master at once, the cabin's tubes flicker up, then the desk, then the
        # glow strips and LEDs. A group already on dips and comes back, as on a reboot.
        _timeline("lights_on", "Lights on", LIGHTS_ON_MS, [
            _lane("power_master", (0, 1.0, "linear")),
            _lane("power_cabin", (100, 0.0, "hold"), (180, 1.0, "linear"), (260, 0.15, "linear"),
                  (360, 0.9, "linear"), (460, 0.3, "linear"), (900, 1.0, "ease_out")),
            _lane("power_desk", (700, 0.0, "hold"), (1500, 1.0, "ease_in_out")),
            _lane("power_glow", (1300, 0.0, "hold"), (LIGHTS_ON_MS, 1.0, "ease_in_out"))]),
        # Lights off: from wherever each group is, the glow first, the cabin last.
        _timeline("lights_off", "Lights off", LIGHTS_OFF_MS, [
            _lane("power_glow", (700, 0.0, "ease_in")),
            _lane("power_desk", (1500, 0.0, "ease_in")),
            _lane("power_cabin", (LIGHTS_OFF_MS, 0.0, "ease_in"))]),
        # Monitors on: one after another, each holding as it is, then flickering on.
        _timeline("monitors_on", "Monitors on", 200 + SCREEN_STEP_MS * (n - 1) + 320, [
            _lane("screen_" + cell, (t, 0.8, "hold"), (t + 50, 0.1, "linear"),
                  (t + 120, 0.9, "linear"), (t + 320, 1.0, "ease_out"))
            for cell, t in ((c, 200 + SCREEN_STEP_MS * i) for i, c in enumerate(SCREENS))]),
        # Monitors off: the other way round, each snapping to black in its turn.
        _timeline("monitors_off", "Monitors off", 150 + 150 * (n - 1), [
            _lane("screen_" + cell, (150 + 150 * i, 0.0, "hold"))
            for i, cell in enumerate(reversed(SCREENS))]),
        # The jump to warp: from wherever the drive is, slow and then faster; and back out.
        _timeline("warp_in", "Go to warp", WARP_IN_MS, [_lane("warp", (WARP_IN_MS, 1.0, "ease_in"))]),
        _timeline("warp_out", "Drop out of warp", WARP_OUT_MS,
                  [_lane("warp", (WARP_OUT_MS, 0.0, "ease_out"))]),
        # The drift: loops until "Hold steady" starts, which eases the ship back.
        dict(_timeline("drift", "Drift", DRIFT_MS,
                       [_lane("drift_" + a, *drift_points(a)) for a in DRIFT_DEG]),
             loop="loop", stops=[{"type": "timeline", "timeline_id": "drift_settle", "edge": "starts"}]),
        _timeline("drift_settle", "Hold steady", DRIFT_SETTLE_MS,
                  [_lane("drift_" + a, (DRIFT_SETTLE_MS, 0.5, "ease_in_out")) for a in DRIFT_DEG]),
    ]


def play(tid):
    return {"type": "timeline.play", "timeline_id": tid}


def holo(value):
    return {"type": "channel.set_value", "channel_id": "holo", "value": value}


# What a person plays, in this order on NOTES' notes after the views': (its name, the key
# after Ctrl+Alt, the action). The hologram's keys are hologram.py's (H, Shift+H).
CONTROLS = [
    ("Lights on", "KeyL", play("lights_on")),
    ("Lights off", "Shift+KeyL", play("lights_off")),
    ("Monitors on", "KeyM", play("monitors_on")),
    ("Monitors off", "Shift+KeyM", play("monitors_off")),
    ("Hologram on", None, holo(1.0)),
    ("Hologram off", None, holo(0.0)),
    ("Go to warp", "KeyW", play("warp_in")),
    ("Drop out of warp", "Shift+KeyW", play("warp_out")),
    ("Drift", "KeyD", play("drift")),
    ("Hold steady", "Shift+KeyD", play("drift_settle")),
]


if __name__ == "__main__":
    # Updates the sequences of a cockpit already in a running JStream (JS_TOKEN and JS_MCP
    # as for ../jstream/mcp.py), as after changing a timing here: `python3 ship_sequences.py`
    # sets every one again, or name some, as in `python3 ship_sequences.py drift`.
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "jstream"))
    from mcp import batch, init
    want = set(sys.argv[1:])
    init()
    _, ok = batch([{"type": "timeline.set", "scene_id": "cockpit", "timeline": t} for t in timelines()
                   if not want or t["timeline_id"] in want], "ship sequences")
    print("done" if ok else "FAILED")
