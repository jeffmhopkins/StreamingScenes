"""The cockpit's hologram: a holographic display that projects up out of the instrument
on the dash, over MCP. A module import_show.py calls, and a command line:

    python3 hologram.py add [scene]      # add the rig to `cockpit` (or scene), off
    python3 hologram.py show             # show it
    python3 hologram.py hide             # hide it
    python3 hologram.py source <id>      # show any source on it: a camera, a capture
    python3 hologram.py standin          # back to the stand-in picture

Everything is generic JStream: cards in the 3D scene with the built-in `hologram` effect
and the `additive` blend, shown and hidden by timelines of `item.show`, `item.hide` and
`item.toggle` cues. The beam and the panel materialise as they are shown: a motion
modifier on the `shown` clock drives each one's `reveal` from 0 to 1. `add` binds
Ctrl+Alt+H to toggle it and Ctrl+Alt+Shift+H to hide it.

In a JStream with sequences (protocol 0.170), `add(..., channels=True)` makes the show and
the hide sequences with lanes: the channels `holo_beam` and `holo_panel` drive the
`reveal`s, so the beam rises and then the panel builds up from the bottom, and on the way
out the panel dissolves and then the beam sinks, before the cues hide the cards. The
channel `holo` is the switch, 0 to 1: its rising past one half starts the show sequence and
its falling the hide, so Ctrl+Alt+H sets it to 1, Ctrl+Alt+Shift+H to 0, and anything that
sets it (a cue, an input such as a JTunnel Mod) shows and hides the hologram too.

The rig, in the model's metres (glTF: +y up, the pilot faces -z):
- the projector's lens, a small glow on the dash, below the monitors, dim while off, and a
  flare over it while on;
- the beam, a light cone standing on it up to the panel;
- the panel, a 16:9 card floating over the dash, above the monitors and in front of the
  windshield, facing the pilot, with a slow bob;
- a faint sheet of light 6 cm in front of the panel;
- a point light in front of the beam, in the hologram's colour, that throws its glow on
  the dash, the monitors and the desk while it is shown.

The panel's top stays under the overhead console's lower edge as the wide view sees it:
that camera's eye is at the panel's height, so moving the panel nearer alone never clears
the console, and the panel sits a little lower and nearer than it first did, at about the
same size on screen.

The light takes one of the 8 lights a model is lit by only while the hologram is shown (a
hidden light lights nothing and takes no slot). `add` puts it first in stacking
order, so it is always among the 8.

The panel shows `holo_feed`, an image source holding the 2D cockpit's caller still, until
`source <id>` (an `item.set_source` on `holo_card`) puts any other source there: a webcam
or a screen capture made in the Sources panel. Every ID starts with `holo_`. In the DAW
show, sources.py points the card at a subscene, `src_holo`, that switches between the DAW
pages and that feed; `source <id>` then points the subscene's feed slot and selects it.

The cards are drawn in stacking order, after the model (`add` turns off the scene
cameras' `depth_sort`, keyframes' included): by box-centre depth they would sort behind
the cabin, whose centre is nearer the camera, and only show through the windows.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

from mcp import asset, batch, init, op  # noqa: E402
from shots import S, p  # noqa: E402

ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
ART = os.path.join(HERE, "hologram")
STANDIN = os.path.join(ROOT, "starship-cockpit", "pages", "caller.png")
COLOR = os.environ.get("HOLO_COLOR", "#5ad2ff")

CARD, BEAM, LENS, FLARE, HAZE = "holo_card", "holo_beam", "holo_lens", "holo_flare", "holo_haze"
LIGHT = "holo_light"
FEED = "holo_feed"
SHOW, HIDE, TOGGLE = "holo_show", "holo_hide", "holo_toggle"
TOGGLE_KEY, HIDE_KEY = "Ctrl+Alt+KeyH", "Ctrl+Alt+Shift+KeyH"

# Where the rig stands, in model metres. The panel's top (with the haze's 8% more and the
# bob) stays under 1.59 m, where the overhead console's lower edge hides it from the wide
# view, and its bottom over the monitor case from the seat; the lens sits 15 mm over the
# dash, which slopes down toward the pilot.
LENS_AT = (0.0, 0.776, -1.20)
PANEL_AT = (0.0, 1.385, -1.20)
PANEL_W, PANEL_H = 0.64, 0.36
# The hologram's light: in front of the beam, a little over the monitors' bottom edge, so
# it lights the dash, the monitors' faces and the desk. HOLO_LIGHT sets its strength; 0
# leaves it out.
LIGHT_AT = (0.0, 1.0, -1.10)
LIGHT_INTENSITY = float(os.environ.get("HOLO_LIGHT", "1.6"))
LIGHT_RANGE_PX = 1000.0
# How long the beam and then the panel take to materialise, from the bottom up.
BEAM_REVEAL_S, PANEL_REVEAL_S = 0.25, 0.5
BEAM_TOP = PANEL_AT[1] - PANEL_H / 2

# Each card's effect. The same kind on both keyframes, so a Move glides its numbers.
CARD_FX = dict(tint=0.85, see_through=0.45, brightness=1.5, lines=0.35, spacing=3.0,
               speed=24.0, sweep=0.4, sweep_period=3.5, edge=0.6, edge_width=10.0,
               flicker=0.2, glitch=0.15, fringe=1.5, grain=0.08)
BEAM_FX = dict(tint=1.0, see_through=0.0, brightness=1.8, lines=0.2, spacing=4.0,
               speed=-60.0, sweep=0.0, edge=0.0, flicker=0.35, glitch=0.0, fringe=0.0,
               grain=0.15)
HAZE_FX = dict(tint=1.0, see_through=0.0, brightness=1.0, lines=0.0, sweep=0.3,
               sweep_period=3.5, edge=0.0, flicker=0.3, glitch=0.0, fringe=0.0, grain=0.1)
LENS_FX = dict(tint=1.0, see_through=0.0, brightness=1.6, lines=0.0, sweep=0.0,
               edge=0.0, flicker=0.25, glitch=0.0, fringe=0.0, grain=0.0)


def _must(result, what):
    text, ok = result
    if not ok:
        sys.exit(f"{what} failed: {text[:400]}")
    return text


def _geo(at, w, h, **kw):
    q = p(*at)
    g = {"center": {"x": q["x"], "y": q["y"]}, "size": {"width": w * S, "height": h * S},
         "depth_px": q["z"]}
    g.update(kw)
    return g


def _pop(seconds):
    """A modifier that raises the hologram effect's `reveal` from 0 to 1 over `seconds`
    from when the item is shown (the `shown` clock); the kind keeps it at 1 after."""
    return {"modifier_id": "pop", "property": "effect", "enabled": True, "clock": "shown",
            "effect": {"filter_id": "holo_fx", "param": "reveal"},
            "kind": "drift", "rate_per_s": 1.0 / seconds}


def _fx(reveal, look):
    return dict(look, color=COLOR, reveal=reveal)


def _image(sid, name, path):
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": "image"}, "settings": {"file": asset(path)}}


def _timeline(tid, name, cues):
    return {"timeline_id": tid, "name": name, "duration_ms": max(c[0] for c in cues) + 100,
            "cues": [{"at_ms": at, "action": {"type": action, "item_id": item}}
                     for at, action, item in sorted(cues, key=lambda c: c[0])]}  # in time order


def _reveal(channel):
    """A modifier that raises the hologram effect's `reveal` with `channel`, 0 to 1."""
    return {"modifier_id": "pop", "property": "effect", "enabled": True, "clock": "engine",
            "effect": {"filter_id": "holo_fx", "param": "reveal"}, "kind": "channel",
            "channel_id": channel, "smoothing_ms": 0, "curve": "linear", "from": 0.0, "to": 1.0}


def _lane(channel, *points):
    return {"target": {"channel": channel},
            "points": [{"at_ms": at, "value": v, "curve": c} for at, v, c in points]}


# The show and the hide, in milliseconds: the beam rises, then the panel builds; the panel
# dissolves, then the beam sinks.
BEAM_UP, PANEL_FROM, PANEL_UP = 250, 120, 620
PANEL_DOWN, BEAM_DOWN = 450, 750


def _sequences(scene, holo_inputs=()):
    """The show and hide sequences with lanes, the `holo` switch that starts them (with
    `holo_inputs`, its inputs), and the keys that set it."""
    chans = [{"channel_id": "holo", "name": "Hologram", "default": 0.0, "inputs": list(holo_inputs)},
             {"channel_id": "holo_beam", "name": "Hologram beam"},
             {"channel_id": "holo_panel", "name": "Hologram panel"}]
    show = _timeline(SHOW, "Hologram on", [(0, "item.show", FLARE), (0, "item.show", BEAM),
                                           (PANEL_FROM, "item.show", CARD),
                                           (PANEL_FROM, "item.show", HAZE)] + _lit(0, "show"))
    show["duration_ms"] = PANEL_UP
    # From nothing: each lane holds at 0 until its card shows, then rises.
    show["lanes"] = [_lane("holo_beam", (0, 0.0, "linear"), (BEAM_UP, 1.0, "ease_out")),
                     _lane("holo_panel", (0, 0.0, "linear"), (PANEL_FROM, 0.0, "linear"),
                           (PANEL_UP, 1.0, "ease_out"))]
    # Each stops on the other's edge, so a hide's late cues never hide a show that
    # followed it.
    show["starts"] = [{"type": "channel", "channel_id": "holo", "edge": "rises"}]
    show["stops"] = [{"type": "channel", "channel_id": "holo", "edge": "falls"}]
    hide = _timeline(HIDE, "Hologram off", [(PANEL_DOWN, "item.hide", CARD), (PANEL_DOWN, "item.hide", HAZE),
                                            (BEAM_DOWN, "item.hide", BEAM), (BEAM_DOWN, "item.hide", FLARE)]
                     + _lit(BEAM_DOWN, "hide"))
    hide["duration_ms"] = BEAM_DOWN
    # From wherever they are: the panel first, then the beam.
    hide["lanes"] = [_lane("holo_panel", (PANEL_DOWN, 0.0, "ease_in")),
                     _lane("holo_beam", (PANEL_DOWN, 1.0, "linear"), (BEAM_DOWN, 0.0, "ease_in"))]
    hide["starts"] = [{"type": "channel", "channel_id": "holo", "edge": "falls"}]
    hide["stops"] = [{"type": "channel", "channel_id": "holo", "edge": "rises"}]
    return ([{"type": "channel.set", "channel": c} for c in chans] + [
        {"type": "item.set_motion", "item_id": BEAM, "motion": [_reveal("holo_beam")]},
        {"type": "item.set_motion", "item_id": CARD, "motion": [_bob(), _reveal("holo_panel")]},
        {"type": "item.set_motion", "item_id": HAZE, "motion": [_reveal("holo_panel")]},
    ] + ([
        # The light comes up with the beam and goes on with the panel. Opacity modifiers
        # multiply, so the beam's scales it from 0 and the panel's from a half: 0 with
        # neither, half with the beam alone, full with both.
        {"type": "item.set_motion", "item_id": LIGHT, "motion": [
            _dim("beam", "holo_beam", -1.0), _dim("panel", "holo_panel", -0.5)]},
    ] if LIGHT_INTENSITY > 0 else []) + [
        {"type": "timeline.set", "scene_id": scene, "timeline": show},
        {"type": "timeline.set", "scene_id": scene, "timeline": hide},
        {"type": "hotkey.set", "chord": TOGGLE_KEY,
         "action": {"type": "channel.set_value", "channel_id": "holo", "value": 1.0}},
        {"type": "hotkey.set", "chord": HIDE_KEY,
         "action": {"type": "channel.set_value", "channel_id": "holo", "value": 0.0}},
    ])


def _lit(at, how):
    """The light's cue in a show (`how` "show"), hide ("hide") or toggle ("toggle")
    timeline, at `at` ms; none without the light."""
    return [(at, f"item.{how}", LIGHT)] if LIGHT_INTENSITY > 0 else []


def _dim(mid, channel, at0):
    """A modifier that scales the light's opacity by 1 + `at0` while `channel` reads 0, and
    leaves it while it reads 1."""
    return {"modifier_id": mid, "property": "opacity", "enabled": True, "clock": "engine",
            "kind": "channel", "channel_id": channel, "smoothing_ms": 0, "curve": "linear",
            "from": at0, "to": 0.0}


def _bob():
    return {"modifier_id": "bob", "property": "y", "enabled": True, "clock": "engine",
            "kind": "oscillate", "shape": "sine", "amplitude": 4.0, "period_ms": 3200,
            "phase": 0.0}


def edits(scene="cockpit", channels=False, holo_inputs=()):
    """The edits that add the rig, switched off, to the 3D scene `scene`, on top of what
    it holds; with `channels`, its show and hide as sequences with lanes."""
    beam_h = BEAM_TOP - LENS_AT[1]
    beam_at = (0.0, LENS_AT[1] + beam_h / 2, LENS_AT[2])

    def add(item, source, g, look, reveal, appear, delay=0, visible=False, opacity=1.0):
        return [
            {"type": "item.add", "scene_id": scene, "item_id": item, "source_id": source,
             "geometry": g},
            {"type": "item.set_blend", "item_id": item, "blend": "additive"},
            {"type": "item.set_opacity", "item_id": item, "opacity": opacity},
            {"type": "filter.add", "owner": {"type": "item", "item_id": item}, "chain": "video",
             "filter_id": "holo_fx", "kind": "hologram", "settings": _fx(reveal, look)},
            {"type": "item.set_transition", "item_id": item, "transition": {
                "delay_ms": delay, "easing": "inherit", "glide": "auto",
                "appear": appear, "disappear": appear}},
            {"type": "item.set_visible", "item_id": item, "visible": visible},
        ]

    e = [
        _image(FEED, "Hologram feed (swap for a camera or capture)", STANDIN),
        _image("holo_beam_art", "Hologram beam", os.path.join(ART, "beam.png")),
        _image("holo_lens_art", "Hologram lens", os.path.join(ART, "glow.png")),
        _image("holo_haze_art", "Hologram haze", os.path.join(ART, "haze.png")),
    ]
    # The lens idles dim; the flare over it, the beam and the panel come and go.
    e += add(LENS, "holo_lens_art", _geo(LENS_AT, 0.09, 0.09, billboard=True), LENS_FX, 1.0,
             "fade", visible=True, opacity=0.35)
    e += add(FLARE, "holo_lens_art", _geo(LENS_AT, 0.14, 0.14, billboard=True), LENS_FX, 1.0,
             "fade", opacity=1.4)
    # The beam, the panel and the haze start unrevealed: each shows by its `reveal`
    # rising from 0 from the moment it is shown (see `_pop`).
    e += add(BEAM, "holo_beam_art", _geo(beam_at, PANEL_W, beam_h, fit_mode="stretch"),
             BEAM_FX, 0.0, "fade")
    e += add(CARD, FEED, _geo(PANEL_AT, PANEL_W, PANEL_H, fit_mode="fill"), CARD_FX, 0.0,
             "scale", delay=150)
    # A faint sheet of light 6 cm in front of the panel, so the projection reads as light
    # in the air and the two layers part as the camera moves.
    e += add(HAZE, "holo_haze_art", _geo((PANEL_AT[0], PANEL_AT[1], PANEL_AT[2] + 0.06),
                                         PANEL_W * 1.08, PANEL_H * 1.08, fit_mode="stretch"),
             HAZE_FX, 0.0, "fade", delay=150, opacity=0.35)
    if LIGHT_INTENSITY > 0:
        q = p(*LIGHT_AT)
        e += [
            {"type": "source.create", "source_id": LIGHT, "name": "Hologram light",
             "kind": {"type": "builtin", "kind": "light"},
             "settings": {"type": "point", "color": COLOR, "intensity": LIGHT_INTENSITY,
                          "range_px": LIGHT_RANGE_PX}},
            {"type": "item.add", "scene_id": scene, "item_id": LIGHT, "source_id": LIGHT,
             "geometry": {"center": {"x": q["x"], "y": q["y"]}, "size": {"width": 40, "height": 40},
                          "depth_px": q["z"]}},
            # First in stacking order, so it is among the 8 lights a model is lit by.
            {"type": "item.reorder", "item_id": LIGHT, "index": 0},
            {"type": "item.set_transition", "item_id": LIGHT, "transition": {
                "delay_ms": 0, "easing": "inherit", "glide": "auto",
                "appear": "fade", "disappear": "fade"}},
            {"type": "item.set_visible", "item_id": LIGHT, "visible": False},
        ]
    e += [
        {"type": "item.set_motion", "item_id": BEAM, "motion": [_pop(BEAM_REVEAL_S)]},
        {"type": "item.set_motion", "item_id": CARD, "motion": [_bob(), _pop(PANEL_REVEAL_S)]},
        {"type": "item.set_motion", "item_id": HAZE, "motion": [_pop(PANEL_REVEAL_S)]},
        {"type": "timeline.set", "scene_id": scene, "timeline": _timeline(
            SHOW, "Hologram on", [(0, "item.show", FLARE), (0, "item.show", BEAM),
                                  (120, "item.show", CARD),
                                  (120, "item.show", HAZE)] + _lit(0, "show"))},
        {"type": "timeline.set", "scene_id": scene, "timeline": _timeline(
            HIDE, "Hologram off", [(0, "item.hide", CARD), (0, "item.hide", HAZE), (250, "item.hide", BEAM),
                                   (250, "item.hide", FLARE)] + _lit(0, "hide"))},
        {"type": "timeline.set", "scene_id": scene, "timeline": _timeline(
            TOGGLE, "Hologram on or off", [(0, "item.toggle", FLARE), (0, "item.toggle", BEAM),
                                           (120, "item.toggle", CARD),
                                           (120, "item.toggle", HAZE)] + _lit(0, "toggle"))},
        {"type": "hotkey.set", "chord": TOGGLE_KEY,
         "action": {"type": "timeline.play", "timeline_id": TOGGLE}},
        {"type": "hotkey.set", "chord": HIDE_KEY,
         "action": {"type": "timeline.play", "timeline_id": HIDE}},
    ]
    if channels:
        # The lanes' motion, timelines and keys replace the cue-only ones. A toggle of the
        # cards alone would leave them unrevealed, so the keys set the `holo` switch instead.
        keep = [x for x in e if x["type"] not in ("hotkey.set", "item.set_motion", "timeline.set")]
        e = keep + _sequences(scene, holo_inputs)
    return e


def show_action():
    return {"type": "timeline.play", "timeline_id": SHOW}


def hide_action():
    return {"type": "timeline.play", "timeline_id": HIDE}


def stacking(camera):
    """`camera` drawing its items in stacking order, so the rig draws after the model."""
    return dict(camera, depth_sort=False)


def add(scene="cockpit", cameras=None, channels=False, holo_inputs=()):
    """Adds the rig to `scene`, switched off. `cameras` maps each scene (the 3D scene and
    its keyframes) to its camera, which is sent again with `depth_sort` off. `channels`
    makes its show and hide sequences with lanes (protocol 0.170)."""
    _must(batch(edits(scene, channels, holo_inputs), "hologram"), "hologram")
    if cameras:
        _must(batch([{"type": "scene.set_camera", "scene_id": sid, "camera": stacking(cam)}
                     for sid, cam in cameras.items()], "hologram cameras"), "hologram cameras")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    init()
    if cmd == "add":
        from shots import SHOTS
        scene = sys.argv[2] if len(sys.argv) > 2 else "cockpit"
        add(scene, {scene: SHOTS["cockpit"]} if scene == "cockpit" else None)
        print("added, off: Ctrl+Alt+H shows or hides it, Ctrl+Alt+Shift+H hides it")
    elif cmd in ("show", "hide"):
        # With sequences, set the `holo` switch, so its edges and the keys stay in step;
        # without the channel, play the timeline.
        _, ok = op({"type": "channel.set_value", "channel_id": "holo",
                    "value": 1.0 if cmd == "show" else 0.0}, quiet=True)
        if not ok:
            _must(op(show_action() if cmd == "show" else hide_action()), cmd)
    elif cmd in ("source", "standin") and (cmd == "standin" or len(sys.argv) > 2):
        # With switchable sources (sources.py), the panel shows the subscene `src_holo`:
        # point its feed slot at the source and select that slot (key 5). Without, point
        # the card itself.
        sid = FEED if cmd == "standin" else sys.argv[2]
        _, ok = op({"type": "item.set_source", "item_id": "src_holo_feed", "source_id": sid})
        if ok:
            _must(op({"type": "timeline.play", "timeline_id": "holo_feed"}), "holo_feed")
        else:
            _must(op({"type": "item.set_source", "item_id": CARD, "source_id": sid}), "item.set_source")
    else:
        sys.exit(__doc__)
