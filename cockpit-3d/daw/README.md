# The DAW cockpit

The 3D cockpit with every screen and many of its lights following a Bitwig session that
JStream receives as JTunnel state. The session is simulated: Jeff's funk song (v42, from
Jclap's `demos/funk-song`) played out as the keys the JTunnel Bitwig extension sends
(`clock`, `transport`, `grid`, `scenes`, `track/0`… `track/7` with their clip slots,
`mixer`, `meters`, `notes`, `device`, `clip`, `markers`), in the extension's own shapes
(Jclap `plugins/jtunnel/bitwig/JTunnel.control.js` and `src/state.cpp`'s `clockJson`),
over the real wire protocol. Nothing in the scene knows it is a simulation: the same
scene follows a real Bitwig with the JTunnel plugin.

| File | What it does |
|---|---|
| `prep.py` | Turns the funk song into `session.json`: the arrangement, tempo and chords from v42's `song.py`, the e-piano and lead notes and the lead's breath from the note lists v42's own script writes, the drums and bass notes from onsets in the MP3, and each track's meter from its band of the MP3's spectrum. |
| `session.json` | That timeline, so a render needs no Jclap checkout. |
| `sim.py` | `Session` plays the timeline as JTunnel state, `Tunnel` sends it: it waits for JStream's subscribe and answers with state packets (type 4), in pieces of at most 1,200 bytes. `python3 sim.py session.json` plays it in real time. |
| `pages/daw.html` | The seven DAW screens (`?view=transport`, `arrange`, `device`, `notes`, `mixer`, `clip`, `scenes`), drawn only from the page API's live data (`jstream.data()`), so a held clock draws the same picture every time. |
| `build_daw.py` | Builds the scene over MCP: the screens atlas, the cockpit, its lights, the data modifiers, reflections and filters. |
| `glow.py` | Lays a card over each of the model's screens, from the corners in the model's README, so `build_daw.py` can make them glow. |
| `render_daw.py` | Renders on the held clock: each frame sends the session's state, steps the clock, sets the camera by the song's section and snapshots. |

## What follows the data

| In the cockpit | Driven by | How |
|---|---|---|
| The desk's pad surface: the clip launcher (8 tracks × 8 scenes, blinking while a clip is queued) | `track/N` `slots[].queued`, `state`, `color` | a `grid` source, cells mode, `state_field = "queued,state"` |
| The desk's meter bridge, tracks and master | `meters` `tracks`, `master` | two `grid` sources, bars mode |
| The seven screens | every key | browser sources with `page_api_data` |
| The screens and the launcher glowing (they bloom, and show bright in the reflections) | every key, through the atlas | a lit card over each screen with `surface.emissive` (`glow.py`) |
| A light over each launcher column, in its track's colour, lighting the desk and the cabin | `meters.tracks.N.0` | `data` modifier on the light's opacity |
| The cabin lights: up while the transport plays, down through the break | `transport.playing`, `track/5.stopped` | `data` modifiers, smoothed over 1.2 to 1.5 s |
| The sky's light, brighter while a chorus plays | `track/0.slots.2.state`, `slots.5.state` | `data` modifier on the environment light's `intensity` |
| The model's red, green, blue and amber LEDs and orange strips | the drums', bass's, keys', master's and lead's meters | `data` modifiers on the materials' `emissive_strength`, by material name |
| The cabin's light strips, on the beat | `clock.beatPhase` | the same, on `light_strip` |

A model is lit by at most 8 lights besides the ambient and the environment, so with the
glow (the default) those are the sun, the cabin and the six pad lights. `GLOW=0` builds
the earlier set: no cards, a light per track around the cabin, the desk's and the
screens' glow. `GLOW_SCREENS`, `GLOW_DESK`, `PAD_INTENSITY` and `PAD_RANGE` tune it. The
probe is 128 px (`PROBE_RES`) so the reflected stars stay soft.

The camera is the one thing the render script moves: it follows the song's sections. Its
focus is close to infinite on every shot, with a slight depth of field only where it sits
close to the desk, a screen or a side console (`CLOSE` in `render_daw.py`).

## Running it

It needs a JStream with the `grid` kind (ADR-0171 decision 9), data modifiers (decision
3), page data (decision 10) and, for the reflections, reflection probes (ADR-0170), built
with its `cef` feature and the browser helper beside it.

```sh
jstream-daemon --port 4455 --token-file ~/jstream-token --jtunnel-accept Bitwig@127.0.0.1:47251
python3 -m http.server 8765 --bind 127.0.0.1 --directory pages &
PAGES=http://127.0.0.1:8765 python3 build_daw.py
python3 render_daw.py session.json frames/   # or: … frames/ <first s> <last s>
ffmpeg -framerate 30 -i frames/f%04d.png -itsoffset 2 -i funk-song-v42.mp3 \
  -map 0:v -map 1:a -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 256k -shortest daw-cockpit.mp4
```

The session starts with 2 s of stopped transport (the first scene queued and blinking),
so the song goes in 2 s late. The render resends every key each frame: a frame takes
longer than a second of wall time, and JStream lets a key go stale 3 s after it was last
sent, as it should for a live sender.

To regenerate `session.json` from a Jclap checkout:
`python3 prep.py <Jclap>/demos/funk-song session.json`.
