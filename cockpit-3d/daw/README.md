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
| `pages/daw.html` | The seven DAW screens (`?view=transport`, `arrange`, `device`, `notes`, `mixer`, `clip`, `scenes`) the desk's note grid (`?view=iso&w=600`) and meter bridge (`?view=bridge&w=348`), each over a page of its unlit pads (`isopads`, `bridgepads`), the console's small displays (`?view=panels&w=320`) and the consoles' amber readouts and small LEDs (`?view=readouts&w=640&h=540`), drawn only from the page API's live data (`jstream.data()`), so a held clock draws the same picture every time. |
| `import_show.py` | Imports the whole show into a running JStream in one go, as a new project: `build_daw.py`'s cockpit, the camera views as sequences with a hotkey each, the cockpit's sequences (lights, monitors, hologram, warp), two 2D scenes, scene hotkeys, and warm scenes. See [Importing the show](#importing-the-show). |
| `show_tour.py` | The Cockpit tour, a show (JStream ADR-0210) that runs through the cockpit for an audience: power up, the seat, the desk, the monitors, the consoles, warp, the hologram, the 2D desk and power down, with a script in every bookmark's note. See [The cockpit tour](#the-cockpit-tour). |
| `add_show.py` | Adds the Cockpit tour to a DAW show imported before it existed, in a running JStream. |
| `views.py` | The camera views, in model metres: the ones `render_daw.py` glides along the song and `import_show.py` turns into sequences, and the channels and lanes those sequences move (`sequences()`). |
| `ship_sequences.py` | The cockpit's sequences: the lights and the monitors powering on and off, the jump to warp and back, and the ship's drift, with their keys. See [Cockpit sequences](#cockpit-sequences). |
| `build_daw.py` | Builds the scene over MCP: the screens atlas, the cockpit, its lights, the channels the switches and the warp are, the data modifiers, reflections and filters. The screens' pages go in inline, so nothing serves them. |
| `glow.py` | Places a card over any rectangle of the screens atlas, from the screens' corners in the model's README. `build_daw.py` lays a glowing card over each page and grid with it. |
| `serve_pages.py` | Serves `pages/` with threads and a deep accept queue, for `PAGES=…` while editing a page: `python -m http.server` queues only 5 connections, and the seven screens load at once. |
| `render_daw.py` | Renders on the held clock: each frame sends the session's state, steps the clock, sets the camera by the song's section and snapshots. |

## What follows the data

| In the cockpit | Driven by | How |
|---|---|---|
| The desk's pad surface: an isomorphic note grid for the selected track, as a grid instrument lays it out (a semitone to the right, a fourth up a row, the lowest row nearest the player), its playing notes lit on every pad of their pitch in the track's colour, each C faintly; it starts on the C at or below the lowest note the track has played, and a note above or below its range folds onto it by whole octaves, so any range shows. The pads are raised silicone caps, matte when unlit and lit from under when playing, with the light brightest in the middle and spilling onto the desk; a pad lights at once and dims over 350 ms when its note ends (the page's `FADE_MS`, timed by the data's clock while the transport plays, so held-clock renders repeat). The unlit pads are a page of their own under the lit ones (`isopads`), which the cabin and desk switches dim, so with the lights off only the lit pads show | `grid.selectedTrack`, `notes.tracks[N]` (`[pitch, velocity]`), `track/N.color` | the page's `iso` view, a browser source with `page_api_data` |
| …or, with `DESK_GRID=clips`, the clip launcher (8 tracks × 8 scenes, blinking while a clip is queued) | `track/N` `slots[].queued`, `state`, `color` | a `grid` source, cells mode, `state_field = "queued,state"` |
| The button panel right of the centre console's readouts: a mini clip launcher, 8 tracks × 8 scenes, a playing clip full in its track's colour, a queued one blinking on the beat, the selected track marked under its column | `track/N` `slots[]`, `color`; `grid.selectedTrack`; `clock.beats` | the `panels` page (its `launcher` cell) on the model's `live_panels` |
| The centre console's left readout: the selected track's last note (name and octave, C3 = 60) and its velocity, as a number and a bar | `notes.tracks[N]`, `grid.selectedTrack` | `panels` (`note`) |
| The centre console's right readout: how busy the selected track is, RATE (the notes it started over the last bar, as segments and a number) and POLY (the notes it holds now, up to 8) | `notes.tracks[N]`, `clock.beats`, `grid.selectedTrack` | `panels` (`density`) |
| The other small readouts: the section, next section, tempo, selected track and device as text (left wing); bar and beat (left wing, aft); the beat in the bar as four dots (right wing, aft); a dot per track while it plays a note (centre); every track's level and the master's as bars (overhead); the master's and the selected track's recent level as scrolling traces (right wing; overhead); the master's and the selected track's level as segment strips (centre, far left) | `markers`, `clock`, `device`, `meters`, `notes`, `grid.selectedTrack` | `panels` (`status`, `position`, `beats`, `activity`, `levels`, `masterWave`, `trackWave`, `strips`); `tools/live_panels.py` names which readout shows which |
| The desk's meter bridge: each track's left and right and the master's, 18 silicone segments each, green to red (the master cyan to amber), each segment dimming over `FADE_MS` as the level falls | `meters` `tracks`, `master` | the page's `bridge` view, over its unlit segments (`bridgepads`), dimmed by the cabin and desk switches as the note grid's unlit pads are |
| The seven screens | every key | browser sources with `page_api_data` |
| The launcher's lit pads, the meters and the screens glowing | every key, through the atlas | the depth bloom at a low threshold (0.4); `GLOW_CARDS=1` also lays a lit, emissive card over each page and grid (`glow.py`), which shows only once cards sort after the model (ADR-0107 decision 7 composites items by their centres' depth) |
| A light over each launcher column, in its track's colour, lighting the desk and the cabin (the lead and its echo share one over their two columns) | `meters.tracks.N.0` | `data` modifier on the light's opacity, from a floor of 55%, over 220 ms (`LEVEL_MS`), so it swells with the band rather than strobing on each hit; the shared light has one for each track, each half as deep |
| The warp's glow: a blue-white light pouring in through the windshield as the warp builds, so a jump to warp lights the cabin even with every switch off | the `warp` channel (CC 30, Mod 6, the warp sequences) | a `channel` modifier on a directional light's opacity, dark at rest and full (`WARP_LIGHT`, 3.0) at full warp; no switch dims it. `WARP_LIGHT=0` leaves it out |
| The cabin lights: up while the transport plays, down through the break | `transport.playing`, `track/5.stopped` | `data` modifiers, smoothed over 1.2 to 1.5 s |
| The ship's warp drive and orientation: the sky streams past as the warp comes up, and the sky and the starlight turn around the cabin as the ship yaws, pitches and rolls | MIDI CCs from Bitwig on channel `SHIP_CC_CHANNEL` (16) from the sender `SHIP_CC_INPUT` (`Bitwig`): `SHIP_CC_WARP` (30) takes the warp from rest to full, and `SHIP_CC_YAW` (31), `SHIP_CC_PITCH` (32) and `SHIP_CC_ROLL` (33) each turn the ship a whole turn over the CC's travel (right, nose up, right wing down), all smoothed over `SHIP_CC_SMOOTHING_MS` (250). `WARP`, `SHIP_YAW`, `SHIP_PITCH` and `SHIP_ROLL` set where they rest. With a JStream that has ADR-0187, each jump to warp travels where the ship points: straight ahead from wherever the heading, pitch and roll have turned the sky, which swings at most `WARP_LOOK_DEG` (10) at warp; out of warp the sky stays where the jump left it and the controls turn it from there (`WARP_AIM=sky` keeps the older behaviour). On an older one, turning moves where the warp streams from, so hold the heading while at warp. The sky follows pitch and roll with a JStream that has ADR-0182; an older one turns it on the heading only | a `channel` modifier on the environment light's `warp` following the channel `warp`, which CC 30, [Mod](#jtunnel-mods) 6 and the [warp sequences](#cockpit-sequences) drive (a `midi` modifier on a JStream without channels), and `channel` modifiers on the `turn`, `tilt` and `rotation` of three nested 3D groups (the ship's rig, ADR-0164) that hold the sky and the starlight, following `ship_yaw`, `ship_pitch` and `ship_roll`, which CCs 31 to 33 and [Mods](#jtunnel-mods) 8 to 10 drive (`midi` modifiers without channels) |
| The sky's light, brighter while a chorus plays | `track/0.slots.2.state`, `slots.5.state` | `data` modifier on the environment light's `intensity` |
| Every other amber readout on the consoles and overhead (25 of them), each keeping its old look: seven-segment digits count the notes played (all of them, or a track's), the bar and beat, the tempo or a device parameter; bar graphs show the selected device's eight parameters (dim at the value, bright at the modulated value), the tracks' levels, or the twelve pitch classes the notes light and leave fading; text lines list the device's parameters and values, the last notes started, or counters (a track's notes modulo 5, 7, 11 or 13, the section, the bar); segment strips show three device parameters, three tracks' levels, or three note counters that each count to a prime and start again; scopes draw the notes a track holds as waves, as loud as the track, its last note ringing on between notes; and dot matrices step a row on every 3rd, 5th, 7th, 11th or 13th note, so the rows walk at their own rates and the pattern never quite repeats | `device.params`, `notes`, `meters`, `clock`, `markers` | the page's `readouts` view, in the space the side monitors gave up (`tools/live_readouts.py`): what each readout shows comes from its old picture's number, so readouts of a look differ |
| The small LEDs (366: the buttons', the toggles', the knobs' and the indicator slits'), each on its own: about half toggle every Nth note of a track (N 2, 3, 5, 7, 11 or 13), some flash on every Nth note, some light while a track's level is over a threshold, some chase across the consoles on the beat, and a few are steady status lights. Red LEDs follow the drums, green the bass, blue the keys, amber any track that plays | `notes`, `meters`, `clock` | the same page, a 4 × 4 cell each |
| The larger LEDs (the monitors' light bar, the pillar markers, the ledge and desk lights, the overhead lamp) and orange strips | the drums', bass's, keys', master's and lead's meters | `data` modifiers on the materials' `emissive_strength`, by material name |
| The cabin's light strips, on the beat | `clock.beatPhase` | the same, on `light_strip` |

## Light switches

Five MIDI CCs switch the cockpit's lights in groups, each fading over `SWITCH_FADE_MS`
(2000 ms, a one-pole fade: about two thirds of the way in that time). They come on
channel `CC_CHANNEL` (16) from the sender `CC_INPUT` (`Bitwig`), from `SWITCH_FIRST` (40)
up:

| CC | Group | What it switches |
|---|---|---|
| 40 | Cabin | the overhead cabin light, the ambient fill and the starlight; half the desk's unlit pads |
| 41 | Desk | the five pad lights over the launcher (with `GLOW=0`, the track lights, the desk's and the screens' glow); the other half of the desk's unlit pads |
| 42 | Screens | every screen and the desk's grid: a black cover over the screens atlas, and the glowing cards with `GLOW_CARDS=1` |
| 43 | Glow | the model's own LEDs and light strips (every material's glow strength), and the live readouts and small LEDs (a black cover over their page) |
| 44 | Master | all four, so only the sky lights the cabin and reflects off it |

A CC up (64 or more, 127 fully) switches its group off, and down switches it back on
(`SWITCH_UP=off`, the default): JStream reads a CC as 0 until it is first sent, so the
cockpit is lit when the show opens. `SWITCH_UP=on` turns that round, and then the
cockpit is dark until each switch is sent (with channels, below, it starts lit either way,
since a CC only counts once it moves). A switch that sits between the two dims its group
part way. `SWITCHES=0` builds without the CCs (with channels, the switch channels stay).

Each switch is a `midi` motion modifier on every light of its group, beside the data
modifiers already there: it adds -1 to a light's opacity (a light's strength is its
intensity times its opacity), +1 to the black cover's, -0.5 to the desk's unlit pads'
(the Cabin and Desk switches each; -1 for the Master), and -3 to the model's glow
strength, which is a multiplier of 1 at rest that the LEDs' data drives raise by up to
1.6. A model takes at most 8 motion modifiers, and the cockpit already has 6 data ones,
so the Glow switches drive every material's glow at once (`emissive_strength` with no
`material`). That needs a JStream where a glow strength with no material reaches every
material; an older one leaves the LEDs and strips lit under the Glow and Master switches,
and everything else still switches. The sky's environment light has no switch.

In a JStream with channels (ADR-0183, protocol 0.169) each switch is a channel,
`power_cabin`, `power_desk`, `power_screens`, `power_glow` and `power_master` (1 on, 0
off, starting on), and its CC is one input of it; the modifiers follow the channel. So
the [cockpit's sequences](#cockpit-sequences) switch the same lights, and whichever of
the CC and a sequence moved last wins. With channels the screens have a cover each
instead of one over the atlas, each following its own channel, `screen_center`,
`screen_left`, `screen_right`, `screen_ovl`, `screen_ovr`, `screen_side_l`,
`screen_side_r`, `screen_desk` and `screen_panels`, which follows `power_screens`: CC 42
still switches them all, and a sequence can light them one at a time. `CHANNELS=0`
builds the CCs straight onto the lights, as a JStream without channels gets.

### JTunnel Mods

With channels, every control a person plays is also a JTunnel modulation param: a channel
reads its Mod (the sender's `params` key, `values.N` for Mod N+1) as one more input, and
JStream names the Mod after the channel (ADR-0181), so the JTunnel plugin in Bitwig lists
"Master power", "Warp" and so on. Map a knob, a fader or automation to the Mod in Bitwig.
They read from `MOD_INPUT` (default `DAW_INPUT`, `Bitwig`), the JTunnel sender to accept
with "Use this sender's state" on, and `MODS=0` leaves them out. Each Mod only takes over
once it first moves, and whichever input moved last wins, so the CCs, the keys and the
sequences keep working beside it.

| Mod | Channel | 0 | 1 |
|---|---|---|---|
| 1 | `power_master` | every light and monitor off | on |
| 2 | `power_cabin` | cabin lights off | on |
| 3 | `power_desk` | desk lights off | on |
| 4 | `power_glow` | LEDs and strips off | on |
| 5 | `power_screens` | every monitor off | on |
| 6 | `warp` | at rest | full warp |
| 7 | `holo` | hologram hidden (crossing one half plays the hide) | shown (crossing one half plays the show) |
| 8 | `ship_yaw` | heading at rest | a whole turn right |
| 9 | `ship_pitch` | pitch at rest | a whole turn nose up |
| 10 | `ship_roll` | roll at rest | a whole turn right wing down |
| 11 to 19 | `screen_center`, `screen_left`, `screen_right`, `screen_ovl`, `screen_ovr`, `screen_side_l`, `screen_side_r`, `screen_desk`, `screen_panels` | that monitor off | on |

The switches fade over `SWITCH_FADE_MS` and the ship over `SHIP_CC_SMOOTHING_MS`, as their
CCs do. The hologram's `holo_beam` and `holo_panel` belong to its sequences and have no
Mod. The camera's channels (`cam_*`, see [Camera views](#camera-views)) have no Mod either,
so Mods 20 to 32 stay free: assign one to a camera channel in JStream (the channel's
inputs) to play it from Bitwig.

A model is lit by at most 8 lights besides the ambient and the environment, so with the
glow (the default) those are the sun, the cabin, the warp's glow and the five pad lights.
The hologram's light counts only while the hologram is shown, and it is first in stacking
order, so then the last pad light gives up its slot (JStream logs once that the scene has
more lights than a model is lit by; that is expected). `GLOW=0` builds the earlier set: no
cards, a light per track around the cabin, the desk's and the screens' glow, of which the
first 8 light the model. `GLOW_CARDS`, `GLOW_SCREENS`, `GLOW_DESK`, `PAD_INTENSITY`, `PAD_RANGE`, `BLOOM_AT`,
`BLOOM` and `LEVEL_MS` tune it. The bloom's radius is 16 px. `render_daw.py` waits
`WARM_S` seconds (3) at the first frame for the pages, the data and the probe. Its frames smooth the band's lights only on a JStream with ADR-0173 (#1620): an engine without it draws each snapshot with no output running at the meters' raw levels, so the lights strobe on every hit whatever `LEVEL_MS` says.

The camera is the one thing the render script moves: it follows the song's sections. Its
focus is close to infinite on every shot, with a slight depth of field only where it sits
close to the desk, a screen or a side console (`CLOSE` in `render_daw.py`).

## Importing the show

The cockpit is also baked into [`jstream-demos.json`](../../jstream-demos.json) at the repo's
root, beside the feature tour, with its views on Ctrl+Shift+1 to 0, - and = there; open that
to skip the import. To build it into a project of its own:

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
| Scenes | `DAW cockpit` (3D, with a sequence a view), `DAW desk 2D` (the launcher, the meters, the transport, the mixer and the arrangement, flat), `Be right back` (a title over the transport) |
| Views | Ctrl+Alt+1 wide, 2 behind the seat, 3 the pilot's seat, 4 the desk, 5 the centre monitor, 6 the left, 7 the right, 8 overhead, 9 out the windshield, 0 the desk low, - the left console, = the right console. Each glides there in `GLIDE_MS` (1800) from wherever the camera is; see [Camera views](#camera-views) |
| Scenes' hotkeys | Ctrl+Alt+F1 the cockpit, F2 the 2D desk, F3 be right back, each a fade of `FADE_MS` (600) |
| Hologram | Ctrl+Alt+H shows the hologram over the dash, Ctrl+Alt+Shift+H hides it (without sequences, Ctrl+Alt+H shows or hides it). It shows the `holo_feed` source; see [The hologram](#the-hologram). A JStream without the `hologram` filter imports the rest of the show and says so |
| Show | the Cockpit tour (`show_tour.py`), on a JStream with shows (protocol 0.177); see [The cockpit tour](#the-cockpit-tour) |
| Warm | the studio keeps `WARM` (3) scenes warm, so the cockpit's sources keep running while a 2D scene is on |
| Sequences | Ctrl+Alt+L lights on, Ctrl+Alt+Shift+L lights off, Ctrl+Alt+M monitors on, Ctrl+Alt+Shift+M monitors off, Ctrl+Alt+W go to warp, Ctrl+Alt+Shift+W drop out of warp, Ctrl+Alt+D drift, Ctrl+Alt+Shift+D hold steady; see [Cockpit sequences](#cockpit-sequences) |
| MIDI | with `NOTES=1`, notes from 36 (C1) up on channel `NOTE_CHANNEL` (16) switch the views in the order above, then from 48 (C2) up play lights on, lights off, monitors on, monitors off, hologram on, hologram off, go to warp, drop out of warp, drift and hold steady, from a JTunnel plugin sending a Bitwig track's MIDI, once the app accepts that plugin's sender too |
| Light switches | CCs 40 to 44 on channel 16 from `Bitwig` fade the Cabin, Desk, Screens and Glow lights and all of them (the master) off and on; see [Light switches](#light-switches). They are always on, whatever `CC` says |
| Camera CCs | with `CC=1` (a JStream whose cameras take MIDI, JStream #1631; CCs 28 and 29 and autofocus need protocol 0.167, and without it the import maps 20 to 27 and says so; a JStream whose cameras don't take MIDI imports the rest without them), CCs from `CC_FIRST` (20) up on channel `CC_CHANNEL` (16) from the sender `CC_INPUT` (`Bitwig`) offset the camera in every view: 20 right, 21 up, 22 forward, 23 pan right, 24 tilt up, 25 zoom in, 26 focus further, 27 more blur (aperture), 28 roll clockwise, 29 past its middle turns autofocus off. `CC=1` also turns on each view's depth of field, and autofocus where JStream has it. Each rests at the view until its CC first moves, and is smoothed over `CC_SMOOTHING_MS` (50), the autofocus switch not at all |

The app hears the hotkeys while another application, such as Bitwig, has the focus. An
agent switches the views with `timeline.play` on a `view_…` sequence (`view_cockpit` is
the wide view). Without reflection probes in the JStream it runs on, the cockpit builds
without reflections and says so.

### The cockpit tour

A show, "Cockpit tour", that walks an audience through the cockpit in about three minutes.
Open the Show panel, pick it and press Play. Each bookmark pauses, and its note is a script
for whoever presents; Continue goes on.

| Bookmark | On program | What the show does |
|---|---|---|
| Pre-show | Be right back | loops until Continue |
| Power up | the cockpit, wide | plays `lights_on`, then `monitors_on` |
| The pilot's seat | the cockpit | behind the seat, then the seat |
| The desk | the cockpit | the desk, then the desk low |
| The monitors | the cockpit | the centre, left and right monitors |
| Overhead and the consoles | the cockpit | overhead, then the left and right consoles |
| Warp | the cockpit | out the windshield; `warp_in`, then `warp_out` 12 s later |
| Hologram | the cockpit | the seat; `holo_show`, then `holo_hide` |
| The same data in 2D | DAW desk 2D | a fade to the flat desk |
| Power down | the cockpit, wide | `monitors_off`, then `lights_off`; the end goes back to Pre-show |

A small tag scene, `tour_tag` ("DAW COCKPIT · BITWIG OVER JTUNNEL"), sits over the cockpit
on an overlay track. The views, lights, monitors, warp and hologram are cues on a sequence
track that play the sequences above, so the show moves nothing a hotkey doesn't. On a
JStream without the hologram's filter its two cues do nothing. A project imported before
the show existed gets it with `python3 add_show.py`; save the project afterwards.

### Camera views

Each view is a sequence (JStream ADR-0184), not a keyframe. The cockpit keeps one camera,
the wide view's, and ten channels (ADR-0183) offset it, each named for what 1 does:

| Channel | Name | 0 to 1 spans |
|---|---|---|
| `cam_x`, `cam_y`, `cam_z` | Camera X (right), Camera Y (up), Camera Z (back) | the views' positions and 30 cm past them each way |
| `cam_tx`, `cam_ty`, `cam_tz` | Camera aim X (right), aim Y (up), aim Z (back) | the point it looks at, the views' and 60 cm past them |
| `cam_fov` | Camera field of view | 15° to 100° |
| `cam_roll` | Camera roll (clockwise) | -45° to 45°, level at one half |
| `cam_focus`, `cam_blur` | Camera focus, Camera blur | the views' focus and 60 cm past it; blur 0 to 20 px (only with `DOF=1` or `CC=1`) |

Each default is the wide view. Any of them can be given an input in JStream, a JTunnel
Mod or a CC, to play it by hand; it then takes the camera from where the views left it. A view's sequence, `view_<shot>`, has a lane on each channel with one
point at `GLIDE_MS`, eased in and out, and no point at 0. So it starts from the channel's
value at that moment and glides from wherever the camera is: from a view, halfway through
a glide to another, or where the Bitwig camera CCs left it, which still add on top. The
latest view to start takes the channels, and the one it interrupts lets go. A view never
switches program: the cockpit stays on, and the sequence moves only the camera. So a
view is also something a longer sequence, a cue or a trigger can start, and its channels
are live values another control can take over.

A JStream without sequences (before protocol 0.170) refuses them, and the import makes
the views keyframes of the cockpit instead, switched with a `glide` move preset, as
before; `SEQUENCES=0` does that on purpose. `VIEW_SMOOTHING_MS` (40) is how closely the
camera follows its channels.

### Cockpit sequences

With sequences, `import_show.py` adds `ship_sequences.py`'s sequences to the cockpit.
Each moves the channels `build_daw.py` makes, so the Bitwig CCs on the same channels
still work, and whichever moved last wins. An agent plays one with `timeline.play`.

| Sequence | Keys (after Ctrl+Alt) | What it does |
|---|---|---|
| `lights_on` | L | The master on at once; the cabin's tubes flicker up, then the desk's lights come up, then the glow strips and LEDs, over 2.4 s. A group already on dips and comes back, like a reboot. |
| `lights_off` | Shift+L | From wherever each group is: the glow goes first, then the desk, the cabin last, over 2.6 s. |
| `monitors_on` | M | The monitors one after another, the centre first and the desk and panels last, each flickering on, 180 ms apart. One already on flickers in its turn. |
| `monitors_off` | Shift+M | The other way round, each snapping to black in its turn, 150 ms apart. |
| `holo_show`, `holo_hide` | H shows, Shift+H hides | The hologram projecting in and dissolving out; see [The hologram](#the-hologram). |
| `warp_in` | W | The sky's warp from wherever it is to full over 4 s, slow at first. |
| `warp_out` | Shift+W | Back to rest over 2.5 s, slowing at the end. |
| `drift` | D | The ship drifting, as if adrift in space: it yaws, pitches and rolls a few degrees at a time, slowly and aimlessly, around wherever it points, and keeps going until held steady. See [The drift](#the-drift). |
| `drift_settle` | Shift+D | Hold steady: stops the drift and eases the ship back to where it points over 6 s. |

The lights and the monitors are separate: lights off leaves the monitors lit, and the
master switch is the lights' alone in a sequence, though its CC still darkens everything.
The warp is a channel, `warp`, that CC 30 and Mod 6 are also inputs of; the heading, pitch
and roll are channels too (`ship_yaw`, `ship_pitch`, `ship_roll`, CCs 31 to 33, Mods 8 to
10). With JStream's
ADR-0187 it travels where the ship points (see [What follows the data](#what-follows-the-data)).

### The drift

`drift` is a loop of 2.5 minutes (`DRIFT_MS`) that turns the ship a little on its own, so
the view out of the windshield wanders as if the ship were adrift. It moves three channels
of its own, `drift_yaw`, `drift_pitch` and `drift_roll`, which `build_daw.py` adds on top
of the heading, pitch and roll on the same three groups of the rig: each turns the ship
`DRIFT_DEG` either way over its 0 to 1 (yaw 8°, pitch 5°, roll 6°), and none at its middle,
where it rests. So the ship drifts around wherever it points: the arrival, pinned within
9° of where the warp ended, stays in the windshield, the ship's CCs still turn it while it
drifts, and a jump to warp goes where it points at that moment.

Each angle is a sum of four slow waves, a whole number of them a loop, with random phases
from a fixed seed (`DRIFT_WAVES`, `DRIFT_SEED` in `ship_sequences.py`), so the three angles
never line up and the drift has no visible pattern. The lane holds the waves' turning
points, eased in and out between them, so the ship slows to a stop each time it turns on
one axis while the others keep moving, every 5 to 30 s; the loop starts and ends on the
same turning point, so it has no seam. The first pass glides in from wherever the ship is.
`drift_settle` (Hold steady) stops `drift` as it starts (a `stops` trigger) and eases the
three back to the middle over 6 s.

### Where a warp arrives

With a JStream that has ADR-0188, each warp drops out in front of something new: one of
the twelve pictures in [`arrivals/`](arrivals), picked at random as the warp ends and
pinned in the sky a little off straight ahead, so it is in view when you arrive. It lights
the cabin faintly in its own colour (`ARRIVAL_LIGHT`, 0.6). `sky_arrivals.py` puts them in
a group scene, `arrivals`, and sets the sky's `sky_pictures` to it.

The picture fades out as the warp builds and back in as it drops. The warp here follows
the `warp` channel, so it never sits above its own setting, and before JStream's ADR-0224
([#1789](https://github.com/jeffmhopkins/JStream/pull/1789)) that left the next picture
unpicked until the warp reached rest, where it popped in, and a warp aimed ahead dropped
the last one within half a second of starting. With ADR-0224 both fade with the deep sky.

The big hazy ones (the emission and reflection nebulae and the spiral galaxy), which
melt into the sky, come up twice as often as the rest (`WEIGHT` in `sky_arrivals.py`,
an item each time), so now and then one follows itself. The ring nebula is rendered
hazy too: its shell's light is spread wide, so its rim melts into a broad halo.

Each is sized for what it is (`SIZE` in `sky_arrivals.py`, its width across the sky):

| Picture | Width |
|---|---|
| Emission nebula, spiral galaxy, reflection nebula | 70° to 80°, most of the window |
| Ring nebula, black hole | 50° |
| Ringed giant, ice giant (with their rings) | 36°, 30° |
| Violet giant, ocean world, desert world, grey moon, lava world | 24° down to 15°, a planet's disc about 0.8 of that, so they look a good way off |

With `SUNS=1`, each planet arrives with its star (a yellow one, or an orange one for the
lava world and the violet giant), placed where the planet's lit side faces it: for most,
100° to 140° away, back over a shoulder, so turning the ship finds it. The star is then
what lights the cabin. That needs ADR-0198's companion pictures, which an older JStream
doesn't have (it would leave those planets out), so `SUNS` is off by default for now.
`ARRIVALS=0` leaves the sky without pictures. A JStream without ADR-0188 refuses the
settings and the pictures in one batch, so nothing of them is left (checked on
alpha.9), and the build says so and goes on.

The pictures are original, rendered by `arrivals/src/render_all.py` with numpy and Pillow
alone: the black hole is ray traced through a Schwarzschild metric, the planets are lit
spheres with atmospheres and ring shadows, and the nebulae and galaxy are layers of gas,
dust and stars. It writes them at 1024 pixels (rendered at 2048) and writes
`arrivals/sun_directions.json`, each planet's sun and where it is.

## The hologram

A holographic display that projects up out of the dash, the 3D
version of the 2D cockpit's incoming-transmission hologram: the projector's lens flares,
a beam rises from it, and a 16:9 panel floats over the dash in front of the windshield,
tinted blue, see-through where the picture is dark, with scanlines, a sweep band, an edge
glow, flicker and the odd glitch, and a faint sheet of light 6 cm in front of it. A light in
its colour comes up with the beam and the panel and lights the dash, the monitors and the
desk around it. It is made of cards in the cockpit's 3D space, so panning the camera shows
it in depth.

The panel floats 1.2 m ahead of the pilot's eye, over the centre monitor, 0.64 × 0.36 m.
Its top stays under the overhead console's lower edge as the wide view sees it: that
camera's eye is level with the top, so moving the panel nearer alone doesn't clear the
console. Its bottom stays clear of the monitor case from the pilot's seat.
`hologram.py` builds it, and `import_show.py` calls it.

| | |
|---|---|
| Show, hide | With sequences: Ctrl+Alt+H sets the channel `holo` to 1 and Ctrl+Alt+Shift+H to 0, as Mod 7 does; its rising past one half starts `holo_show` and its falling `holo_hide`, so an agent sends `channel.set_value` on `holo`, as `python3 hologram.py show` and `hide` do. Without: Ctrl+Alt+H (the timeline `holo_toggle`), Ctrl+Alt+Shift+H (`holo_hide`); `holo_show` shows it |
| What it shows | the image source `holo_feed` (the 2D cockpit's caller still) until `item.set_source` on `holo_card` names another, such as a webcam or a screen capture made in the Sources panel: `python3 hologram.py source <source id>` |
| Its look | JStream's built-in `hologram` video filter on each card (`holo_fx`), with the `additive` blend; `HOLO_COLOR` changes the colour (default `#5ad2ff`) |
| Its pieces | `holo_lens` (dim while off), `holo_flare`, `holo_beam`, `holo_card`, `holo_haze` and `holo_light`; the art is in `hologram/` (`make_art.py` draws it) |
| Its light | `holo_light`, a point light in the hologram's colour in front of the beam, shown and hidden with the cards. With sequences it is at 0 before the beam, half with the beam and full with the panel (two opacity modifiers, which multiply: `holo_beam` scales it from 0, `holo_panel` from a half). `HOLO_LIGHT` sets its strength (1.6); 0 leaves it out. It takes one of the model's 8 lights only while shown (see [Light switches](#light-switches)) |

The cards sit behind the cabin model's centre, so JStream would sort them under the
model and show them only through the windows. `hologram.py` turns off `depth_sort` on the
cockpit's camera and on every view's, so items draw in stacking order, the hologram last.

It projects in: the flare comes up, the beam rises out of the lens in a quarter of a
second, and the panel and its haze materialise from the bottom up over half a second
behind a bright scan line. Each is the effect's `reveal` driven from 0 to 1 by a
motion modifier on the `shown` clock, so it plays every time the item is shown, under
any transition. It goes at once.

With sequences (protocol 0.170) the show and the hide are lanes instead: two channels,
`holo_beam` and `holo_panel`, drive the `reveal`s. `holo_show` shows the cards and raises
the beam over 250 ms, then the panel and haze from 120 ms to 620 ms. `holo_hide`
dissolves the panel and haze from wherever they are over 450 ms while the beam stays,
then sinks the beam by 750 ms, and its cues hide the cards when each is gone.

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
