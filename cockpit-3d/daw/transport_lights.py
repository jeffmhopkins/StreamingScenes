"""The transport, shown in front of the left monitor in the desk lights' style, and a
stopwatch under the right monitor (the model's parts from ../tools/add_transport.py):

- four beat lights (`led_beat_1` to `led_beat_4`, amber), the one for the bar's current
  beat lit while the transport plays, each on its channel `beat_1` to `beat_4` ("Beat 1"
  to "Beat 4"), which read JTunnel's `clock` key;
- the play light, green while the transport plays and red while it is stopped, on the
  channel `transport_playing` ("Transport.Playing");
- a seven-segment display on the left wing's readout: the position as bar.beat.sixteenth
  over the tempo (the DAW page's `clocks` view, left half);
- a seven-segment stopwatch on the right wing's readout, under the right monitor: the
  time since its last reset as HH:MM:SS (the same page, right half). The sequence
  `Stopwatch reset` (Ctrl+Alt+R) resets it, and so does JTunnel Mod 25 ("Stopwatch
  reset") moving across its middle either way, so a toggle in Bitwig resets it each flip;
- up top between the overhead monitors, the local time, 24-hour, as HH:MM:SS (the
  page's bottom left), from the clock of the machine JStream runs on.

The Glow and Master switches put the lights out as they do every LED, and the Screens and
Master switches black the displays as they do every screen.

build_daw.py and import_show.py use this for a new build. To add it to a cockpit already in
a running JStream (a project imported before this), first run
`../tools/add_transport.py` on each copy of the model the project uses, then:

    python3 transport_lights.py

MODEL_ITEM (default `model`) names the cockpit's model item; PAGES and DAW_INPUT are as for
build_daw.py. Run again, it replaces what it added before.

A channel only counts an input once it has moved since the engine began following it
(ADR-0183), and `playing` doesn't move until the transport starts or stops, so the play
light also reads the beat's phase moving: green while the transport runs, red once it
stops. Moving the play head while stopped turns it green until the next start or stop.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from live_panels import CLOCKS_AT  # noqa: E402

STOPWATCH_MOD = 25  # pages/daw.html's STOPWATCH_MOD
STOPWATCH_VALUE = "stopwatch.reset"
RESET_MS = 200
RESET_KEY = "KeyR"
# The beat lights stop at a little over half, as the amber desk lights do.
BEAT_DRIVE = (-1.0, -0.45)


def channels(src=None, mod_inputs=lambda n: []):
    """The beat and play channels' `channel.set`s, reading JTunnel's `clock` key from the
    sender `src` (None: any), and `Stopwatch reset`, which only names JTunnel Mod 25 in
    Bitwig (the page reads the Mod itself). `mod_inputs(n)` is the list of inputs reading
    Mod n ([] for none)."""
    sender = {"input": src} if src else {}

    def clock(field, rng, frm, to):
        return {"kind": "data", **sender, "key": "clock", "field": field, "range": list(rng),
                "smoothing_ms": 0, "curve": "linear", "from": frm, "to": to}
    playing = clock("playing", (0.0, 1.0), 0.0, 1.0)
    out = []
    # A beat light's channel is 1 on its beat and 0 off it: the product of a step up just
    # before its beat, a step down just after it, and whether the transport plays.
    for n in range(1, 5):
        out.append({"type": "channel.set", "channel": {
            "channel_id": f"beat_{n}", "name": f"Transport.Beat {n}", "default": 0.0, "combine": "product",
            "inputs": [clock("beat", (n - 0.5, n), 0.0, 1.0), clock("beat", (n, n + 0.5), 1.0, 0.0),
                       dict(playing)]}})
    # The play light: `playing`, and the beat's phase moving. An input takes part once its
    # reading (through its range, before from and to) leaves where it rested, and `latest`
    # follows the one whose reading changed last: so the phase reads through its whole
    # range, to change while the transport runs, and maps every reading to 1. The light is
    # green while the transport runs even if it was already running when the channel
    # began, before `playing` first moved; a stop moves `playing` to 0, and it wins.
    out.append({"type": "channel.set", "channel": {
        "channel_id": "transport_playing", "name": "Transport.Playing", "default": 0.0,
        "inputs": [playing, clock("beatPhase", (0.0, 1.0), 1.0, 1.0)]}})
    out.append({"type": "channel.set", "channel": {
        "channel_id": "stopwatch_reset", "name": "Transport.Stopwatch reset", "default": 0.0,
        "inputs": mod_inputs(STOPWATCH_MOD)}})
    return out


def _drive(mid, channel, material, at0, at1, smoothing=40):
    return {"modifier_id": mid, "property": "source", "enabled": True, "clock": "engine",
            "kind": "channel", "channel_id": channel, "smoothing_ms": smoothing, "curve": "linear",
            "from": at0, "to": at1, "source": {"param": "emissive_strength", "material": material}}


def model_motion():
    """The model item's modifiers for the lights, before the switches' gates (6 of them)."""
    out = [_drive(f"m_beat_{n}", f"beat_{n}", f"led_beat_{n}", *BEAT_DRIVE) for n in range(1, 5)]
    out += [_drive("m_play", "transport_playing", "led_play", -1.0, 0.0),
            _drive("m_stop", "transport_playing", "led_stop", 0.0, -1.0)]
    return out


def clocks_source(page, src=None):
    """The `clocks` page's browser source, with the stopwatch's shared value granted."""
    _, _, w, h = CLOCKS_AT
    return {"type": "source.create", "source_id": "clocks", "name": "Transport, stopwatch and clock",
            "kind": {"type": "builtin", "kind": "browser"},
            "settings": {**page("clocks", w, h), "width": w, "height": h, "fps": 30,
                         "page_api": True, "page_api_data": True,
                         **({"page_api_data_input": src} if src is not None else {}),
                         "page_api_shared_values": True, "page_api_values": "stopwatch.*"}}


def reset_sequence(scene="cockpit"):
    """`Stopwatch reset`: the shared value true for a moment, then false again, and its
    hotkey, Ctrl+Alt+R. The page resets as the value turns true."""
    cue = lambda at, v: {"at_ms": at, "action": {"type": "values.set", "name": STOPWATCH_VALUE, "value": v}}
    return [{"type": "timeline.set", "scene_id": scene, "timeline": {
        "timeline_id": "stopwatch_reset", "name": "Transport.Stopwatch reset", "duration_ms": RESET_MS,
        "lanes": [], "cues": [cue(0, True), cue(RESET_MS, False)]}},
            {"type": "hotkey.set", "chord": "Ctrl+Alt+" + RESET_KEY,
             "action": {"type": "timeline.play", "timeline_id": "stopwatch_reset"}}]


# ---- changing a cockpit already in a running JStream ----

def _main():
    sys.path.insert(0, os.path.join(HERE, "..", "jstream"))
    from mcp import batch, init
    import desk_lights

    pages = os.environ.get("PAGES", "")
    html = open(os.path.join(HERE, "pages", "daw.html"), encoding="utf-8").read()
    src = os.environ.get("DAW_INPUT", "")

    def page(view, width, height):
        if pages:
            return {"url": f"{pages}/daw.html?view={view}&w={width}&h={height}"}
        head = f'<head><script>window.DAW_VIEW="{view}";window.DAW_W={width};window.DAW_H={height}</script>'
        return {"html": html.replace("<head>", head, 1)}

    def follow(mid, channel, at0, at1, **kw):
        m = {"modifier_id": mid, "property": "opacity", "enabled": True, "clock": "engine",
             "kind": "channel", "channel_id": channel, "smoothing_ms": 30, "curve": "linear",
             "from": at0, "to": at1}
        m.update(kw)
        return m

    def glow_gate(group):
        return follow(f"switch_{group}", "power_" + group, -3.0, 0.0, property="source",
                      source={"param": "emissive_strength"})

    def step(edits, what):
        _, ok = batch(edits, what)
        print(("done: " if ok else "FAILED: ") + what)
        return ok

    init()
    # A re-run replaces what an earlier run added: each removal on its own, since one
    # that finds nothing fails. Deleting the sequence removes its hotkey.
    for e in [{"type": "timeline.delete", "timeline_id": "stopwatch_reset"},
              {"type": "item.remove", "item_id": "off_clocks"},
              {"type": "item.remove", "item_id": "a_clocks"},
              {"type": "source.delete", "source_id": "clocks"}]:
        batch([e], "remove an earlier run's " + (e.get("item_id") or e.get("timeline_id") or e["source_id"]))
    model = os.environ.get("MODEL_ITEM", "model")
    x, y, w, h = CLOCKS_AT
    geo = {"center": {"x": x + w / 2, "y": y + h / 2}, "size": {"width": w, "height": h}, "fit_mode": "stretch"}
    def mods(n):
        return [{"kind": "data", **({"input": src} if src else {}), "key": "params",
                 "field": f"values.{n - 1}", "range": [0.0, 1.0], "smoothing_ms": 0,
                 "curve": "linear", "from": 0.0, "to": 1.0}]

    step(channels(src or None, mods) + [{"type": "channel.set", "channel": {
        "channel_id": "screen_clocks", "name": "Screens.Clocks", "default": 1.0,
        "inputs": [{"kind": "channel", "channel_id": "power_screens", "smoothing_ms": 0,
                    "curve": "linear", "from": 0.0, "to": 1.0}]}}],
         "the beat, play, stopwatch and clocks-screen channels")
    step([{"type": "item.set_motion", "scene_id": "cockpit", "item_id": model,
           "motion": model_motion() + desk_lights.model_motion([glow_gate("glow"), glow_gate("master")])}],
         f"the transport lights on their channels (item `{model}`)")
    # The page under the atlas's master cover: in just above the background.
    step([clocks_source(page, src),
          {"type": "item.add", "scene_id": "atlas", "item_id": "a_clocks", "source_id": "clocks", "geometry": geo},
          {"type": "item.reorder", "item_id": "a_clocks", "index": 1},
          {"type": "item.add", "scene_id": "atlas", "item_id": "off_clocks", "source_id": "atlas_off",
           "geometry": geo},
          {"type": "item.reorder", "item_id": "off_clocks", "index": 2},
          {"type": "item.set_motion", "scene_id": "atlas", "item_id": "off_clocks",
           "motion": [follow("screen", "screen_clocks", 0.0, -1.0)]}],
         "the transport and stopwatch displays in the screens atlas")
    step(reset_sequence(), "the Stopwatch reset sequence, Ctrl+Alt+R")


if __name__ == "__main__":
    _main()
