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
| `pages/daw.html` | The seven DAW screens (`?view=transport`, `arrange`, `device`, `notes`, `mixer`, `clip`, `scenes`) the desk's note grid (`?view=iso&w=600`) and the console's small displays (`?view=panels&w=320`), drawn only from the page API's live data (`jstream.data()`), so a held clock draws the same picture every time. |
| `import_show.py` | Imports the whole show into a running JStream in one go, as a new project: `build_daw.py`'s cockpit, the camera views as keyframes with a hotkey each, two 2D scenes, scene hotkeys, and warm scenes. See [Importing the show](#importing-the-show). |
| `views.py` | The camera views, in model metres: the ones `render_daw.py` glides along the song and `import_show.py` turns into keyframes. |
| `build_daw.py` | Builds the scene over MCP: the screens atlas, the cockpit, its lights, the data modifiers, reflections and filters. The screens' pages go in inline, so nothing serves them. |
| `glow.py` | Places a card over any rectangle of the screens atlas, from the screens' corners in the model's README. `build_daw.py` lays a glowing card over each page and grid with it. |
| `serve_pages.py` | Serves `pages/` with threads and a deep accept queue, for `PAGES=…` while editing a page: `python -m http.server` queues only 5 connections, and the seven screens load at once. |
| `render_daw.py` | Renders on the held clock: each frame sends the session's state, steps the clock, sets the camera by the song's section and snapshots. |

## What follows the data

| In the cockpit | Driven by | How |
|---|---|---|
| The desk's pad surface: an isomorphic note grid for the selected track, as a grid instrument lays it out (a semitone to the right, a fourth up a row, the lowest row nearest the player), its playing notes lit on every pad of their pitch in the track's colour, each C faintly; it starts on the C at or below the lowest note the track has played, and a note above or below its range folds onto it by whole octaves, so any range shows | `grid.selectedTrack`, `notes.tracks[N]` (`[pitch, velocity]`), `track/N.color` | the page's `iso` view, a browser source with `page_api_data` |
| …or, with `DESK_GRID=clips`, the clip launcher (8 tracks × 8 scenes, blinking while a clip is queued) | `track/N` `slots[].queued`, `state`, `color` | a `grid` source, cells mode, `state_field = "queued,state"` |
| The button panel right of the centre console's readouts: a mini clip launcher, 8 tracks × 8 scenes, a playing clip full in its track's colour, a queued one blinking on the beat, the selected track marked under its column | `track/N` `slots[]`, `color`; `grid.selectedTrack`; `clock.beats` | the `panels` page (its `launcher` cell) on the model's `live_panels` |
| The centre console's left readout: the selected track's last note (name and octave, C3 = 60) and its velocity, as a number and a bar | `notes.tracks[N]`, `grid.selectedTrack` | `panels` (`note`) |
| The centre console's right readout: how busy the selected track is, RATE (the notes it started over the last bar, as segments and a number) and POLY (the notes it holds now, up to 8) | `notes.tracks[N]`, `clock.beats`, `grid.selectedTrack` | `panels` (`density`) |
| The other small readouts: the section, next section, tempo, selected track and device as text (left wing); bar and beat (left wing, aft); the beat in the bar as four dots (right wing, aft); a dot per track while it plays a note (centre); every track's level and the master's as bars (overhead); the master's and the selected track's recent level as scrolling traces (right wing; overhead); the master's and the selected track's level as segment strips (centre, far left) | `markers`, `clock`, `device`, `meters`, `notes`, `grid.selectedTrack` | `panels` (`status`, `position`, `beats`, `activity`, `levels`, `masterWave`, `trackWave`, `strips`); `tools/live_panels.py` names which readout shows which |
| The desk's meter bridge, tracks and master | `meters` `tracks`, `master` | two `grid` sources, bars mode |
| The seven screens | every key | browser sources with `page_api_data` |
| The launcher's lit pads, the meters and the screens glowing | every key, through the atlas | the depth bloom at a low threshold (0.4); `GLOW_CARDS=1` also lays a lit, emissive card over each page and grid (`glow.py`), which shows only once cards sort after the model (ADR-0107 decision 7 composites items by their centres' depth) |
| A light over each launcher column, in its track's colour, lighting the desk and the cabin | `meters.tracks.N.0` | `data` modifier on the light's opacity, from a floor of 55%, over 220 ms (`LEVEL_MS`), so it swells with the band rather than strobing on each hit |
| The cabin lights: up while the transport plays, down through the break | `transport.playing`, `track/5.stopped` | `data` modifiers, smoothed over 1.2 to 1.5 s |
| The ship's warp drive and heading: the sky streams past as the warp comes up, and the sky and the starlight turn around the cabin as the ship yaws | MIDI CCs from Bitwig on channel `SHIP_CC_CHANNEL` (16) from the sender `SHIP_CC_INPUT` (`Bitwig`): `SHIP_CC_WARP` (30) takes the warp from rest to full, `SHIP_CC_YAW` (31) turns the ship a whole turn right over the CC's travel, both smoothed over `SHIP_CC_SMOOTHING_MS` (250). `WARP` and `SHIP_YAW` set where they rest. Turning also moves where the warp streams from, so hold the heading while at warp | `midi` modifiers on the environment light's `warp` and `turn`, and on the starlight's `turn` |
| The sky's light, brighter while a chorus plays | `track/0.slots.2.state`, `slots.5.state` | `data` modifier on the environment light's `intensity` |
| The model's red, green, blue and amber LEDs and orange strips | the drums', bass's, keys', master's and lead's meters | `data` modifiers on the materials' `emissive_strength`, by material name |
| The cabin's light strips, on the beat | `clock.beatPhase` | the same, on `light_strip` |

A model is lit by at most 8 lights besides the ambient and the environment, so with the
glow (the default) those are the sun, the cabin and the six pad lights. `GLOW=0` builds
the earlier set: no cards, a light per track around the cabin, the desk's and the
screens' glow. `GLOW_CARDS`, `GLOW_SCREENS`, `GLOW_DESK`, `PAD_INTENSITY`, `PAD_RANGE`, `BLOOM_AT`,
`BLOOM` and `LEVEL_MS` tune it. The bloom's radius is 16 px. `render_daw.py` waits
`WARM_S` seconds (3) at the first frame for the pages, the data and the probe. Its frames smooth the band's lights only on a JStream with ADR-0173 (#1620): an engine without it draws each snapshot with no output running at the meters' raw levels, so the lights strobe on every hit whatever `LEVEL_MS` says.

The camera is the one thing the render script moves: it follows the song's sections. Its
focus is close to infinite on every shot, with a slight depth of field only where it sits
close to the desk, a screen or a side console (`CLOSE` in `render_daw.py`).

## Importing the show

`import_show.py` puts everything into a running JStream over MCP, with no other step: no
page server, and no files copied, since the screens' pages go into the project inline and
the models are read from this checkout.

1. Start the JStream desktop app with `--mcp` (its Getting started guide, "Connect an
   agent"), or the daemon with `--token-file`.
2. In the app, turn on "Receive from JTunnel senders" and accept the Bitwig sender, named
   `Bitwig` (`DAW_INPUT` names another). Only a person can change this setting, so it is
   the one step a script can't do. It takes effect when the app next starts.
3. From this folder: `python3 import_show.py` (Python 3 with numpy). It makes a new
   project, `DAW show.json` beside `cockpit-3d/` (numbered if one exists, or give a path),
   builds it and saves it there, so the app opens it again next time.

What it makes:

| | |
|---|---|
| Scenes | `DAW cockpit` (3D, with a keyframe a view), `DAW desk 2D` (the launcher, the meters, the transport, the mixer and the arrangement, flat), `Be right back` (a title over the transport) |
| Views | Ctrl+Alt+1 wide, 2 behind the seat, 3 the pilot's seat, 4 the desk, 5 the centre monitor, 6 the left, 7 the right, 8 overhead, 9 out the windshield, 0 the desk low, - the left console, = the right console. Each glides there in `GLIDE_MS` (1800) |
| Scenes' hotkeys | Ctrl+Alt+F1 the cockpit, F2 the 2D desk, F3 be right back, each a fade of `FADE_MS` (600) |
| Hologram | Ctrl+Alt+H shows or hides the hologram over the dash, Ctrl+Alt+Shift+H hides it. It shows the `holo_feed` source; see [The hologram](#the-hologram). A JStream without the `hologram` filter imports the rest of the show and says so |
| Warm | the studio keeps `WARM` (3) scenes warm, so the cockpit's sources keep running while a 2D scene is on |
| MIDI | with `NOTES=1`, notes from 36 (C1) up on channel `NOTE_CHANNEL` (16) switch the views in the order above, from a JTunnel plugin sending a Bitwig track's MIDI, once the app accepts that plugin's sender too |
| Camera CCs | with `CC=1` (a JStream whose cameras take MIDI, JStream #1631; CCs 28 and 29 and autofocus need protocol 0.167, and without it the import maps 20 to 27 and says so; a JStream whose cameras don't take MIDI imports the rest without them), CCs from `CC_FIRST` (20) up on channel `CC_CHANNEL` (16) from the sender `CC_INPUT` (`Bitwig`) offset the camera in every view: 20 right, 21 up, 22 forward, 23 pan right, 24 tilt up, 25 zoom in, 26 focus further, 27 more blur (aperture), 28 roll clockwise, 29 past its middle turns autofocus off. `CC=1` also turns on each view's depth of field, and autofocus where JStream has it. Each rests at the view until its CC first moves, and is smoothed over `CC_SMOOTHING_MS` (50), the autofocus switch not at all |

The app hears the hotkeys while another application, such as Bitwig, has the focus. An
agent switches the views with `scene.switch` to `cockpit` or a `view_…` keyframe and the
preset `glide`. Without reflection probes in the JStream it runs on, the cockpit builds
without reflections and says so.

## The hologram

A holographic display that projects up out of the dash, the 3D
version of the 2D cockpit's incoming-transmission hologram: the projector's lens flares,
a beam rises from it, and a 16:9 panel floats over the dash in front of the windshield,
tinted blue, see-through where the picture is dark, with scanlines, a sweep band, an edge
glow, flicker and the odd glitch, and a faint sheet of light 6 cm in front of it. It is
made of cards in the cockpit's 3D space, so panning the camera shows it in depth.
`hologram.py` builds it, and `import_show.py` calls it.

| | |
|---|---|
| Show, hide | Ctrl+Alt+H (the timeline `holo_toggle`), Ctrl+Alt+Shift+H (`holo_hide`); `holo_show` shows it. An agent sends `timeline.play` with one of them |
| What it shows | the image source `holo_feed` (the 2D cockpit's caller still) until `item.set_source` on `holo_card` names another, such as a webcam or a screen capture made in the Sources panel: `python3 hologram.py source <source id>` |
| Its look | JStream's built-in `hologram` video filter on each card (`holo_fx`), with the `additive` blend; `HOLO_COLOR` changes the colour (default `#5ad2ff`) |
| Its pieces | `holo_lens` (dim while off), `holo_flare`, `holo_beam`, `holo_card` and `holo_haze`; the art is in `hologram/` (`make_art.py` draws it) |

The cards sit behind the cabin model's centre, so JStream would sort them under the
model and show them only through the windows. `hologram.py` turns off `depth_sort` on the
cockpit's camera and on every view's, so items draw in stacking order, the hologram last.

It projects in: the flare comes up, the beam rises out of the lens in a quarter of a
second, and the panel and its haze materialise from the bottom up over half a second
behind a bright scan line. Each is the effect's `reveal` driven from 0 to 1 by a
motion modifier on the `shown` clock, so it plays every time the item is shown, under
any transition. It goes at once.

```sh
python3 hologram.py add          # into an existing `cockpit` scene (build_daw.py's)
python3 hologram.py show         # or hide, source <id>, standin
```

## Running it

It needs a JStream with the `grid` kind (ADR-0171 decision 9), data modifiers (decision
3), page data (decision 10) and, for the reflections, reflection probes (ADR-0170), built
with its `cef` feature and the browser helper beside it.

```sh
jstream-daemon --port 4455 --token-file ~/jstream-token --jtunnel-accept Bitwig@127.0.0.1:47251
python3 build_daw.py
python3 render_daw.py session.json frames/   # or: … frames/ <first s> <last s>
ffmpeg -framerate 30 -i frames/f%04d.png -itsoffset 2 -i funk-song-v42.mp3 \
  -map 0:v -map 1:a -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 256k -shortest daw-cockpit.mp4
```

`RELOAD_PAGES=1` makes the render load each screen's page again, one at a time
(`source.restart`), before it starts; it's off by default, since a reload can be refused
by the page's request policy and leave that screen blank. The session starts with 2 s of stopped transport (the first scene queued and blinking),
so the song goes in 2 s late. The render resends every key each frame: a frame takes
longer than a second of wall time, and JStream lets a key go stale 3 s after it was last
sent, as it should for a live sender.

To regenerate `session.json` from a Jclap checkout:
`python3 prep.py <Jclap>/demos/funk-song session.json`.
