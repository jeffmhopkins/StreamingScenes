"""The cockpit tour: a JStream show (JStream ADR-0210, protocol 0.177) that runs through the
DAW cockpit for an audience, with a readable script in every bookmark's note.

It plays only what import_show.py makes: the camera views (views.py, as sequences), the
cockpit's sequences (ship_sequences.py: lights, monitors, warp), the hologram's
(hologram.py), and the `desk_2d` and `brb_2d` scenes. It adds one small scene of its
own, `tour_tag`, a corner tag that the show lays over the cockpit.

    edits()  -> the batch that makes `tour_tag` and sets the show
    SHOW     -> the show, as `show.set`'s `show`

A cue whose sequence isn't there (the hologram, on a JStream without its filter) does
nothing when the show reaches it, so the rest of the tour still runs.
"""
from views import view_id

S = 1000
FADE = "fade"  # import_show.py's fade preset


def _play(tid):
    return {"type": "timeline.play", "timeline_id": tid}


def _view(shot):
    return _play(view_id(shot))


# (bookmark id, name, scene on program, length, pausing, [(offset ms, cue id, action)], note)
CHAPTERS = [
    ("preshow", "Pre-show", "brb_2d", 15 * S, False, [],
     "*Be right back slate, looping until you press Continue. The transport on it is live.*\n\n"
     "In a moment I'll take you into the cockpit.\n\n"
     "*Make sure Bitwig is playing, or the simulated session is, then press Continue.*"),
    ("power", "Power up", "cockpit", 14 * S, True, [
        (0, "power_view", _view("cockpit")),
        (300, "power_lights", _play("lights_on")),
        (3000, "power_monitors", _play("monitors_on")),
    ],
     "This is a starship cockpit, and it's a real 3D model: a glTF file that JStream lights "
     "and renders live, with reflections, bloom and depth of field.\n\n"
     "Watch it power up. The lights come up in stages, and then the monitors flicker on one "
     "by one. Each of those is a sequence: a short timeline that moves a few channels.\n\n"
     "Everything on those screens is coming from Bitwig, live, over JTunnel."),
    ("seat", "The pilot's seat", "cockpit", 15 * S, True, [
        (0, "seat_wide", _view("seat_wide")),
        (7 * S, "seat_close", _view("seat")),
    ],
     "Let's sit down. The camera views are sequences too: each one glides the scene camera "
     "from wherever it is to the view, so I can cut between them on a key, a MIDI note or a "
     "cue in this show.\n\n"
     "From the pilot's seat you see the three monitors wrapped around you, and the desk "
     "below them."),
    ("desk", "The desk", "cockpit", 18 * S, True, [
        (0, "desk_view", _view("desk")),
        (9 * S, "desk_low", _view("desk_low")),
    ],
     "The desk is the musician's view. The pad grid is an isomorphic note layout for the "
     "track selected in Bitwig: the notes it's playing light up in that track's colour.\n\n"
     "The bars beside it are the meter bridge, every track and the master. And the lights "
     "over the desk swell with each track's level, in its colour."),
    ("monitors", "The monitors", "cockpit", 24 * S, True, [
        (0, "mon_centre", _view("monitor")),
        (8 * S, "mon_left", _view("monitor_l")),
        (16 * S, "mon_right", _view("monitor_r")),
    ],
     "The centre monitor is the arrangement, with the play head and the song's sections.\n\n"
     "On the left, the transport: tempo, bar and beat, and the section we're in. On the "
     "right, the device on the selected track and its parameters.\n\n"
     "These are web pages drawn from JStream's page API. JStream hands them Bitwig's state, "
     "and they draw it."),
    ("consoles", "Overhead and the consoles", "cockpit", 24 * S, True, [
        (0, "con_over", _view("overhead")),
        (8 * S, "con_left", _view("side_l")),
        (16 * S, "con_right", _view("side_r")),
    ],
     "Overhead, the mixer and Bitwig's scenes. On the left console, the clip that's playing; "
     "on the right, the notes it's sending.\n\n"
     "Every small readout and LED on the consoles is live too: the last note and its velocity, "
     "how busy the track is, the level traces, the device's parameters as bar graphs, scopes "
     "of the notes, and LEDs and dot matrices that step on every 3rd, 5th or 7th note, so the "
     "patterns keep shifting."),
    ("warp", "Warp", "cockpit", 22 * S, True, [
        (0, "warp_view", _view("out")),
        (2 * S, "warp_go", _play("warp_in")),
        (14 * S, "warp_drop", _play("warp_out")),
    ],
     "Out the windshield is the sky: an environment light with stars and nebulae.\n\n"
     "The warp is a channel. A sequence takes it up to full, and a CC or a JTunnel Mod from "
     "Bitwig can drive the same channel, so a knob in the DAW can fly the ship.\n\n"
     "And when we drop out, we arrive somewhere new."),
    ("holo", "Hologram", "cockpit", 14 * S, True, [
        (0, "holo_view", _view("seat")),
        (1500, "holo_on", _play("holo_show")),
        (11 * S, "holo_off", _play("holo_hide")),
    ],
     "Incoming transmission. The hologram projects up out of the dash: a lens flare, a beam, "
     "and a panel showing any source, a camera or a screen capture.\n\n"
     "It's a filter on a regular source, placed in the 3D scene."),
    ("desk2d", "The same data in 2D", "desk_2d", 14 * S, True, [],
     "And not every scene has to be 3D. This is the same live Bitwig data as a flat desk: "
     "the clip launcher, the meters, the transport, the mixer and the arrangement.\n\n"
     "The studio keeps the cockpit warm, so switching back is instant."),
    ("down", "Power down", "cockpit", 12 * S, True, [
        (0, "down_view", _view("cockpit")),
        (1000, "down_monitors", _play("monitors_off")),
        (3000, "down_lights", _play("lights_off")),
    ],
     "And that's the cockpit. Monitors off, lights off.\n\n"
     "Thanks for flying with us.\n\n"
     "*Continue goes back to the pre-show slate.*"),
]


def _build():
    program, bookmarks, cues, overlays = [], [], [], []
    t = 0
    for n, (bid, name, scene, length, pausing, chapter_cues, note) in enumerate(CHAPTERS):
        clip = {"clip_id": "c_" + bid, "scene_id": scene, "length_ms": length}
        # A clip of the same scene as the one before would put it on program again: join them.
        if program and program[-1]["scene_id"] == scene:
            program[-1]["length_ms"] += length
        else:
            if n:
                clip["preset_id"] = FADE
            program.append(clip)
        b = {"bookmark_id": bid, "name": name, "at_ms": t, "note": note}
        if not pausing:
            b["pausing"] = False
        bookmarks.append(b)
        cues += [{"cue_id": cid, "at_ms": t + off, "action": action} for off, cid, action in chapter_cues]
        if scene == "cockpit":
            overlays.append({"clip_id": "tag_" + bid, "scene_id": "tour_tag", "start_ms": t + 600,
                             "length_ms": length - 1200, "fade_in_ms": 500, "fade_out_ms": 400})
        t += length
    # Join the tag's clips that touch, so it stays up across chapters.
    tags = []
    for c in overlays:
        if tags and c["start_ms"] - (tags[-1]["start_ms"] + tags[-1]["length_ms"]) <= 1200:
            tags[-1]["length_ms"] = c["start_ms"] + c["length_ms"] - tags[-1]["start_ms"]
        else:
            tags.append(c)
    return {
        "show_id": "tour_cockpit",
        "name": "Cockpit tour",
        "program": program,
        "overlays": [{"track_id": "v2", "name": "Tag", "clips": tags}],
        "sequences": [{"track_id": "s1", "name": "Views, lights and ship", "cues": cues}],
        "bookmarks": bookmarks,
        "loops": [{"loop_id": "preshow_loop", "name": "Pre-show", "start_ms": 0,
                   "end_ms": CHAPTERS[0][3], "leave": "at_once"}],
        "end": {"type": "go_to", "bookmark_id": "preshow"},
        "preset_id": FADE,
        "next_monitor": "still",
    }, t


SHOW, LENGTH_MS = _build()

TAG_TEXT = "DAW COCKPIT  ·  BITWIG OVER JTUNNEL"


def edits():
    """The tag scene and the show, as one batch of edits."""
    return [
        {"type": "source.create", "source_id": "tour_tag_plate", "name": "Tour tag plate",
         "kind": {"type": "builtin", "kind": "color"},
         "settings": {"color": "#070b12c8", "width": 560, "height": 56}},
        {"type": "source.create", "source_id": "tour_tag_text", "name": "Tour tag text",
         "kind": {"type": "builtin", "kind": "text"},
         "settings": {"text": TAG_TEXT, "size": 30, "face": "condensed_bold", "color": "#ffb040ff"}},
        {"type": "scene.create", "scene_id": "tour_tag", "name": "Tour tag"},
        {"type": "item.add", "scene_id": "tour_tag", "item_id": "tour_tag_plate",
         "source_id": "tour_tag_plate",
         "geometry": {"center": {"x": 64 + 280, "y": 64 + 28}, "size": {"width": 560, "height": 56}},
         "fit_mode": "stretch"},
        {"type": "item.add", "scene_id": "tour_tag", "item_id": "tour_tag_text",
         "source_id": "tour_tag_text",
         "geometry": {"center": {"x": 64 + 280, "y": 64 + 28}, "size": {"width": 520, "height": 40}},
         "fit_mode": "fit"},
        {"type": "show.set", "show": SHOW},
    ]


if __name__ == "__main__":
    import json
    print(json.dumps(SHOW, indent=1))
    print(f"{LENGTH_MS // 60000}:{LENGTH_MS // 1000 % 60:02d}, {len(SHOW['bookmarks'])} bookmarks")
