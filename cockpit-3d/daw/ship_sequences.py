"""The cockpit's sequences (JStream ADR-0184): the lights and the monitors powering on and
off, and the jump to warp and back. import_show.py adds them, with a hotkey each, to a
cockpit build_daw.py built with channels (ADR-0183).

Each sequence moves channels build_daw.py makes, each one more input of its channel, so
the Bitwig CC on the same channel still works and whichever moved last wins:
- `power_cabin`, `power_desk` and `power_glow`, the light groups' switches (1 on), and
  `power_master`, which every group and the monitors also need on;
- `screen_<cell>`, a monitor's switch (1 on), one per atlas cell;
- `warp`, the sky's warp drive (0 at rest, 1 full).

The hologram's show and hide are hologram.py's.
"""

# The monitors, in the order they power on: the centre, then outward and up, the desk last.
SCREENS = ["center", "left", "right", "ovl", "ovr", "side_l", "side_r", "desk", "panels"]

LIGHTS_ON_MS, LIGHTS_OFF_MS = 2400, 2600
SCREEN_STEP_MS = 180
WARP_IN_MS, WARP_OUT_MS = 4000, 2500


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
]
