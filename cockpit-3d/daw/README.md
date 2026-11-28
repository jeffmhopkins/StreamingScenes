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
| `pages/daw.html` | The seven DAW screens (`?view=transport`, `arrange`, `device`, `notes`, `mixer`, `clip`, `scenes`), the 2D desk's note grid (`?view=iso&w=600`) and meter bridge (`?view=bridge&w=348`), each over a page of its unlit pads (`isopads`, `bridgepads`), the console's clip launcher panel (`?view=panels&w=320`, its `launcher` cell), drawn only from the page API's live data (`jstream.data()`), so a held clock draws the same picture every time. While the transport plays, the views that move with the clock (`transport`, `arrange`, `notes`) draw every frame and run the clock on from the last update at the tempo (at most 150 ms, never past the next beat), so what moves moves evenly though updates land out of step with the page's frames; on a held clock, stepped slower than real time, they draw the data alone, and `?smooth=0` (`window.DAW_SMOOTH = 0`) draws only on updates. The still views (`device`, `scenes`, `clip`, `mixer`, `iso`, `bridge`) draw only when what they show changed, so a page paints only what is new. `?s=` (`window.DAW_S`) draws a page that many times sharper (the source is W × H times S): the screens' background and scanlines are layers drawn once, and the lit pads cached sprites, so a sharp page costs little more to draw. |
| `import_show.py` | Imports the whole show into a running JStream in one go, as a new project: `build_daw.py`'s cockpit, the camera views as keyframes in a `Views` folder with a hotkey each, the cockpit's sequences (lights, monitors, hologram, warp), two 2D scenes, scene hotkeys, and warm scenes. See [Importing the show](#importing-the-show). |
| `show_tour.py` | The Cockpit tour, a show (JStream ADR-0210) that runs through the cockpit for an audience: power up, the seat, the desk, the monitors, the consoles, warp, the hologram, the 2D desk and power down, with a script in every bookmark's note. See [The cockpit tour](#the-cockpit-tour). |
| `add_show.py` | Adds the Cockpit tour to a DAW show imported before it existed, in a running JStream. |
| `views.py` | The camera views, in model metres: the ones `render_daw.py` glides along the song and `import_show.py` turns into keyframes of the cockpit (`keyframes()`), filed in a folder (`filing()`). |
| `title.py`, `title/` | The Sound Journal title over the cockpit, and its card (`title/make_title.py` draws `title.png`). See [The Sound Journal title](#the-sound-journal-title). |
| `ship_sequences.py` | The cockpit's sequences: the lights and the monitors powering on and off, the jump to warp and back, and the ship's drift, with their keys. See [Cockpit sequences](#cockpit-sequences). |
| `desk_lights.py`, `desk/` | The desk switched off (`desk/pads-off.png`, the model's own dark pads), and the cockpit's small LEDs in four groups, the channels `Desk lights 1` to `4` on JTunnel Mods 21 to 24, with a twinkle to try them. Run on its own, it changes a cockpit already in a running JStream. See [Desk lights](#desk-lights). |
| `transport_lights.py` | The transport's four beat lights and play light in front of the left monitor, its position and tempo on a seven-segment display there, a stopwatch under the right monitor, with its reset (Ctrl+Alt+R, or Mod 25), and the local time up top between the overhead monitors. Run on its own, it adds them to a cockpit already in a running JStream. See [Transport lights and stopwatch](#transport-lights-and-stopwatch). |
| `sources.py` | What the three main monitors, the hologram and the desk show: a subscene each, with sources to switch between and, on the monitors and the hologram, the selected one's soft key lit. See [Switching what the screens show](#switching-what-the-screens-show). |
| `build_daw.py` | Builds the scene over MCP: the screens atlas, the cockpit, its lights, the channels the switches and the warp are, the data modifiers, reflections and filters. The screens' pages go in inline, so nothing serves them. |
| `glow.py` | Places a card over any rectangle of the screens atlas, from the screens' corners in the model's README. `build_daw.py` lays a glowing card over each page and grid with it. |
| `serve_pages.py` | Serves `pages/` with threads and a deep accept queue, for `PAGES=…` while editing a page: `python -m http.server` queues only 5 connections, and the seven screens load at once. |
| `stress.py` | A heavy, fast-changing Bitwig session over JTunnel, to load-test JStream and the pages: it stands in for the JTunnel plugin on its port and sends a 32 × 32 grid with every slot changing, every meter and note, Mods 1 to 25 moving every tick, tempo sweeps, stops and loop jumps, and an audio stream with dense MIDI. See [Stress test](#stress-test). |
| `render_daw.py` | Renders on the held clock: each frame sends the session's state, steps the clock, sets the camera by the song's section and snapshots. |

## What follows the data

| In the cockpit | Driven by | How |
|---|---|---|
| The button panel right of the centre console's readouts: a mini clip launcher, 8 tracks × 8 scenes, a playing clip full in its track's colour, a queued one blinking on the beat, the selected track marked under its column | `track/N` `slots[]`, `color`; `grid.selectedTrack`; `clock.beats` | the `panels` page (its `launcher` cell) on the model's `live_panels` |
| The seven screens | every key | browser sources with `page_api_data` |
| The screens glowing | every key, through the atlas | the depth bloom at a low threshold (0.4); `GLOW_CARDS=1` also lays a lit, emissive card over each page (`glow.py`), which shows only once cards sort after the model (ADR-0107 decision 7 composites items by their centres' depth) |
| The warp's glow: a blue-white light pouring in through the windshield as the warp builds, so a jump to warp lights the cabin even with every switch off | the `warp` channel (CC 30, Mod 6, the warp sequences) | a `channel` modifier on a directional light's opacity, dark at rest and full (`WARP_LIGHT`, 3.0) at full warp; no switch dims it. `WARP_LIGHT=0` leaves it out |
| The cabin lights: up while the transport plays, down through the break | `transport.playing`, `track/5.stopped` | `data` modifiers, smoothed over 1.2 to 1.5 s |
| The ship's warp drive and orientation: the sky streams past as the warp comes up, and the sky and the starlight turn around the cabin as the ship yaws, pitches and rolls | MIDI CCs from Bitwig on channel `SHIP_CC_CHANNEL` (16) from any input (`SHIP_CC_INPUT` names one): `SHIP_CC_WARP` (30) takes the warp from rest to full, and `SHIP_CC_YAW` (31), `SHIP_CC_PITCH` (32) and `SHIP_CC_ROLL` (33) each turn the ship a whole turn over the CC's travel (right, nose up, right wing down), all smoothed over `SHIP_CC_SMOOTHING_MS` (250). `WARP`, `SHIP_YAW`, `SHIP_PITCH` and `SHIP_ROLL` set where they rest. With a JStream that has ADR-0187, each jump to warp travels where the ship points: straight ahead from wherever the heading, pitch and roll have turned the sky, which swings at most `WARP_LOOK_DEG` (10) at warp; out of warp the sky stays where the jump left it and the controls turn it from there (`WARP_AIM=sky` keeps the older behaviour). On an older one, turning moves where the warp streams from, so hold the heading while at warp. The sky follows pitch and roll with a JStream that has ADR-0182; an older one turns it on the heading only | a `channel` modifier on the environment light's `warp` following the channel `warp`, which CC 30, [Mod](#jtunnel-mods) 6 and the [warp sequences](#cockpit-sequences) drive (a `midi` modifier on a JStream without channels), and `channel` modifiers on the `turn`, `tilt` and `rotation` of three nested 3D groups (the ship's rig, ADR-0164) that hold the sky and the starlight, following `ship_yaw`, `ship_pitch` and `ship_roll`, which CCs 31 to 33 and [Mods](#jtunnel-mods) 8 to 10 drive (`midi` modifiers without channels) |
| The sky's light, brighter while a chorus plays | `track/0.slots.2.state`, `slots.5.state` | `data` modifier on the environment light's `intensity` |

The desk itself follows nothing: its grid controller is switched off, the console's amber
readouts show the model's own pictures, and its small LEDs are the [desk lights](#desk-lights),
which follow only their channels.

## Desk lights

The model's small LEDs, all over the cockpit, are four groups by colour, each one channel
a person or Bitwig drives (`desk_lights.py`). Nothing in the band moves them.

| Channel | Name | Mod | LEDs | 0 | 1 |
|---|---|---|---|---|---|
| `desk_lights_1` | Desk lights 1 | 21 | the red ones (`led_red`) | dark | the model's own glow |
| `desk_lights_2` | Desk lights 2 | 22 | the green ones (`led_green`) | dark | the model's own glow |
| `desk_lights_3` | Desk lights 3 | 23 | the blue ones (`led_blue`) | dark | the model's own glow |
| `desk_lights_4` | Desk lights 4 | 24 | the amber ones (`led_amber`) | dark | 0.55 of the model's glow, so the many of them don't flare under the bloom |

Each starts at 1, so the LEDs are lit until its [Mod](#jtunnel-mods) first moves. Each is
a `channel` modifier on its material's `emissive_strength`, and the Glow and Master
[switches](#light-switches) still put every LED out, whatever its channel reads. The cabin
lights (the overhead light, the fill and the starlight) are in no group: the Cabin switch
keeps them. The cabin's light strips and the orange accent strips glow steadily, under the
Glow and Master switches.

`Desk lights twinkle` (Ctrl+Alt+G) loops a random twinkle, 12 s a pass, on all four
channels, to try them without Bitwig; `Desk lights steady` (Ctrl+Alt+Shift+G) stops it and
brings all four back to full. Whichever moved last of a channel's Mod and a sequence wins.

To change a cockpit already in a running JStream, imported before the desk lights, run
`python3 desk_lights.py` (JS_TOKEN and JS_MCP as for `../jstream/mcp.py`; `MODEL_ITEM`
names the model's item if it isn't `model`), and `python3 ../tools/trim_live_panels.py`
on each copy of the model the project uses.

## Transport lights and stopwatch

In front of the left monitor, in the desk lights' style, a row of LEDs and a seven-segment
display show the transport (`transport_lights.py`; the model's parts come from
`../tools/add_transport.py`):

| Light | Channel | Lit |
|---|---|---|
| Four amber beat lights (`led_beat_1` to `4`) | `beat_1` to `beat_4`, "Beat 1" to "Beat 4" | the bar's current beat, while the transport plays; all dark while it is stopped |
| The play light (`led_play`, `led_stop`) | `transport_playing`, "Transport playing" | green while the transport plays, red while it is stopped |

The channels read JTunnel's `clock` key (`beat`, `playing`), and the Glow and Master
switches put the lights out as they do every LED. A channel counts an input only once it
has moved, and `playing` moves only when the transport starts or stops, so the play light
also reads the beat's phase moving: it is green while the transport runs even when it was
already running as JStream started. Moving the play head while stopped turns it green
until the next start or stop. The display is the left half of the
`clocks` page: the position as bar.beat.sixteenth over the tempo in BPM.

Under the right monitor, on a 13 × 6.5 cm module over the right wing's small readout, the
page's right half is a stopwatch: the time since its last
reset as HH:MM:SS (from the engine's clock, so it starts at the app's start). The sequence
`Stopwatch reset` (Ctrl+Alt+R) resets it, by setting the shared value `stopwatch.reset`
true for a moment, and so does JTunnel Mod 25 crossing its middle either way, so a toggle
in Bitwig resets it at each flip. The channel `stopwatch_reset` only names Mod 25 in
Bitwig.

Up top, between the overhead monitors, a third display on a module over the overhead
console's readout shows the local time, 24-hour, as HH:MM:SS, from the clock of the machine
JStream runs on (the page's bottom left). The Screens and Master switches black all three
displays (the `screen_clocks` channel).

To add them to a cockpit already in a running JStream, run
`python3 ../tools/add_transport.py` on each copy of the model the project uses, then
`python3 transport_lights.py` (JS_TOKEN and JS_MCP as for `../jstream/mcp.py`; `MODEL_ITEM`
names the model's item if it isn't `model`; `PAGES` and `DAW_INPUT` as for `build_daw.py`).
Run again, it replaces what it added before.

## Light switches

Five MIDI CCs switch the cockpit's lights in groups, each fading over `SWITCH_FADE_MS`
(2000 ms, a one-pole fade: about two thirds of the way in that time). They come on
channel `CC_CHANNEL` (16) from any input (`CC_INPUT` names one), from `SWITCH_FIRST` (40)
up:

| CC | Group | What it switches |
|---|---|---|
| 40 | Cabin | the overhead cabin light, the ambient fill and the starlight; the desk's pads, to half |
| 41 | Desk | the desk's pads (with `GLOW=0`, also the track lights, the desk's and the screens' glow) |
| 42 | Screens | every screen and the desk's grid: a black cover over the screens atlas, and the glowing cards with `GLOW_CARDS=1` |
| 43 | Glow | the model's own LEDs ([desk lights](#desk-lights)) and light strips: every material's glow strength |
| 44 | Master | all four, so only the sky lights the cabin and reflects off it |

A CC up (64 or more, 127 fully) switches its group off, and down switches it back on
(`SWITCH_UP=off`, the default): JStream reads a CC as 0 until it is first sent, so the
cockpit is lit when the show opens. `SWITCH_UP=on` turns that round, and then the
cockpit is dark until each switch is sent (with channels, below, it starts lit either way,
since a CC only counts once it moves). A switch that sits between the two dims its group
part way. `SWITCHES=0` builds without the CCs (with channels, the switch channels stay).

Each switch is a `midi` motion modifier on every light of its group, beside the data
modifiers already there: it adds -1 to a light's opacity (a light's strength is its
intensity times its opacity, and a modifier on opacity multiplies it by 1 plus what it
adds), -1 to the black cover's while the switch is on (so the cover, opaque as placed,
clears, and comes back as the switch turns off), -0.5 to the desk's pads' for the
Cabin switch and -1 for the Desk and Master switches, and -3 to the model's glow
strength, which is a multiplier of 1 at rest that the desk lights only lower. The Glow
switches drive every material's glow at once (`emissive_strength` with no `material`). That needs a JStream where a glow strength with no material reaches every
material; an older one leaves the LEDs and strips lit under the Glow and Master switches,
and everything else still switches. The sky's environment light has no switch.

In a JStream with channels (ADR-0183, protocol 0.169) each switch is a channel,
`power_cabin`, `power_desk`, `power_screens`, `power_glow` and `power_master` (1 on, 0
off, starting on), and its CC is one input of it; the modifiers follow the channel. So
the [cockpit's sequences](#cockpit-sequences) switch the same lights, and whichever of
the CC and a sequence moved last wins. The Master switch has a black cover of its own
over the whole atlas, since either it or the screens' switch alone must black the screens
and one cover's modifiers only multiply. With channels the screens have a cover each
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
They read from `MOD_INPUT` (default `DAW_INPUT`; unset, any sender), the JTunnel sender to accept
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
| 20 | `title` | the Sound Journal title off | on |
| 21 to 24 | `desk_lights_1` to `desk_lights_4` | that [group of LEDs](#desk-lights) dark | lit |
| 25 | `stopwatch_reset` | crossing one half either way resets the [stopwatch](#transport-lights-and-stopwatch) | |

The switches fade over `SWITCH_FADE_MS` and the ship over `SHIP_CC_SMOOTHING_MS`, as their
CCs do. The hologram's `holo_beam` and `holo_panel` belong to its sequences and have no
Mod. Mods 26 to 32 stay free.

A model is lit by at most 8 lights besides the ambient and the environment, so with the
glow (the default) those are the sun, the cabin and the warp's glow, and the hologram's
light while the hologram is shown. `GLOW=0` builds the earlier set: no
cards, a light per track around the cabin, the desk's and the screens' glow, of which the
first 8 light the model. `GLOW_CARDS`, `GLOW_SCREENS`, `BLOOM_AT`,
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
2. In the app, turn on "Receive from JTunnel senders" and accept the Bitwig sender. The
   cockpit names no input, so it reads whichever sender sends (in the desktop app, the live
   one), whatever its name. `DAW_INPUT`, `CC_INPUT` and `SHIP_CC_INPUT` name one instead.
   Only a person can change this setting, so it is
   the one step a script can't do. It takes effect when the app next starts.
3. From this folder: `python3 import_show.py` (Python 3 with numpy). It makes a new
   project, `DAW show.json` beside `cockpit-3d/` (numbered if one exists, or give a path),
   builds it and saves it there, so the app opens it again next time.

What it makes:

| | |
|---|---|
| Scenes | `DAW cockpit` (3D, with a keyframe a view, in its `Views` folder), `DAW desk 2D` (the launcher, the meters, the transport, the mixer and the arrangement, flat), `Be right back` (a title over the transport), `Sound Journal` (the Sound Journal title, which its switch puts over program as an overlay) |
| Views | Ctrl+Alt+1 wide, 2 behind the seat, 3 the pilot's seat, 4 the desk, 5 the centre monitor, 6 the left, 7 the right, 8 overhead, 9 out the windshield, 0 the desk low, - the left console, = the right console. Each glides to its keyframe in `GLIDE_MS` (1800) from wherever the camera is; see [Camera views](#camera-views) |
| Scenes' hotkeys | Ctrl+Alt+F1 the cockpit, F2 the 2D desk, F3 be right back, each a fade of `FADE_MS` (600) |
| Hologram | Ctrl+Alt+H shows the hologram over the dash, Ctrl+Alt+Shift+H hides it (without sequences, Ctrl+Alt+H shows or hides it). It shows a subscene, `src_holo`, which starts on the `holo_feed` source; see [The hologram](#the-hologram) and [Switching what the screens show](#switching-what-the-screens-show). A JStream without the `hologram` filter imports the rest of the show and says so |
| Show | the Cockpit tour (`show_tour.py`), on a JStream with shows (protocol 0.177); see [The cockpit tour](#the-cockpit-tour) |
| Warm | the studio keeps `WARM` (3) scenes warm, so the cockpit's sources keep running while a 2D scene is on |
| Sequences | Ctrl+Alt+L lights on, Ctrl+Alt+Shift+L lights off, Ctrl+Alt+M monitors on, Ctrl+Alt+Shift+M monitors off, Ctrl+Alt+W go to warp, Ctrl+Alt+Shift+W drop out of warp, Ctrl+Alt+D drift, Ctrl+Alt+Shift+D hold steady; see [Cockpit sequences](#cockpit-sequences). What each main monitor and the hologram show: Ctrl+Alt+Shift with 1 to 5 (left monitor), 6 to 0 (centre), Y to P (right), Z to B (hologram) and N or K (desk); see [Switching what the screens show](#switching-what-the-screens-show) |
| Sound Journal title | Ctrl+Alt+J fades it in, Ctrl+Alt+Shift+J out; notes 84 and 85 on channel 16, too; see [The Sound Journal title](#the-sound-journal-title) |
| MIDI | with `NOTES=1`, notes from 36 (C1) up on channel `NOTE_CHANNEL` (16) switch the views in the order above, then from 48 (C2) up play lights on, lights off, monitors on, monitors off, hologram on, hologram off, go to warp, drop out of warp, drift and hold steady, then from 58 (A#2) up the screens' sources, five each for the left, centre and right monitors and the hologram (58 to 77) and the desk's two (78, 79), and 84 (C6) and 85 turn the Sound Journal title on and off, from a JTunnel plugin sending a Bitwig track's MIDI, once the app accepts that plugin's sender too |
| Light switches | CCs 40 to 44 on channel 16 from any input fade the Cabin, Desk, Screens and Glow lights and all of them (the master) off and on; see [Light switches](#light-switches). They are always on, whatever `CC` says |
| Camera CCs | with `CC=1` (a JStream whose cameras take MIDI, JStream #1631; CCs 28 and 29 and autofocus need protocol 0.167, and without it the import maps 20 to 27 and says so; a JStream whose cameras don't take MIDI imports the rest without them), CCs from `CC_FIRST` (20) up on channel `CC_CHANNEL` (16) from any input (`CC_INPUT` names one) offset the camera in every view: 20 right, 21 up, 22 forward, 23 pan right, 24 tilt up, 25 zoom in, 26 focus further, 27 more blur (aperture), 28 roll clockwise, 29 past its middle turns autofocus off. `CC=1` also turns on each view's depth of field, and autofocus where JStream has it. Each rests at the view until its CC first moves, and is smoothed over `CC_SMOOTHING_MS` (50), the autofocus switch not at all |

The app hears the hotkeys while another application, such as Bitwig, has the focus. An
agent switches the views with `scene.switch` to a `view_…` keyframe with the preset
`view_glide` (`view_cockpit` is the wide view). Without reflection probes in the JStream it runs on, the cockpit builds
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
on an overlay track. The views are markers on the show's keyframe track, each gliding to its
keyframe with `view_glide`, and the lights, monitors, warp and hologram are cues on a
sequence track that play the sequences above, so the show moves nothing a hotkey doesn't. On a
JStream without the hologram's filter its two cues do nothing. A project imported before
the show existed gets it with `python3 add_show.py`; save the project afterwards.

### Camera views

Each view is a keyframe of the cockpit (JStream ADR-0049), `view_<shot>`, named `View: …`,
with the view's camera. They sit in a folder under the cockpit, `Views` (ADR-0222; a
JStream before scene folders, protocol 0.190, leaves them unfiled and says so). The wide
view is a keyframe too, `view_cockpit`, with the same camera as the cockpit's own, so
every view is in the folder; Ctrl+Alt+F1 puts the cockpit itself on, also wide.

A view's hotkey, note or show marker switches to its keyframe with `view_glide`, a Move of
`GLIDE_MS` (1800), eased in and out as the view sequences were (smoothstep, as a cubic
Bézier, since a Move's own `ease_in_out` is steeper): the camera glides from wherever it is, from a view or
halfway through a glide to another (a switch mid-glide starts from what is on screen,
JStream ADR-0029 §7). Each view's own transition in is `view_glide` too, so a view
glides in however it is switched to: from the Scenes list, Studio's take or a Stream Deck
key as well. The Bitwig camera CCs belong to the cockpit's family, so they offset
every view alike and carry through a glide. To change a view, edit its keyframe's camera
in JStream, as any keyframe's; the hotkeys, notes and the tour follow it.

A JStream with ADR-0226 draws such a glide as the cockpit itself, its ambient occlusion,
bloom and reflections running throughout, through a moving camera, so it looks as the
sequences did. An older one draws the cockpit without those scene filters while a glide
runs (ADR-0180), so the glow around the screens dips for the length of a glide.

### Cockpit sequences

With sequences (protocol 0.170), `import_show.py` adds `ship_sequences.py`'s sequences to the cockpit.
Each moves the channels `build_daw.py` makes, so the Bitwig CCs on the same channels
still work, and whichever moved last wins. An agent plays one with `timeline.play`.

| Sequence | Keys (after Ctrl+Alt) | What it does |
|---|---|---|
| `lights_on` | L | The master on at once; the cabin's tubes flicker up, then the desk's lights come up, then the glow strips and LEDs, over 2.4 s. A group already on dips and comes back, like a reboot. |
| `lights_off` | Shift+L | From wherever each group is: the glow goes first, then the desk, the cabin last, over 2.6 s. |
| `monitors_on` | M | The monitors one after another, the centre first and the desk and panels last, each flickering on, 180 ms apart. One already on flickers in its turn. |
| `desk_twinkle` | G | The [desk lights](#desk-lights) twinkle at random, looping, until `desk_steady`. |
| `desk_steady` | Shift+G | Stops the twinkle and brings the four desk lights back to full over 0.4 s. |
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

`drift` is a loop of 7.5 minutes (`DRIFT_MS`; after a change, `python3 ship_sequences.py drift` sets it again in a running cockpit) that turns the ship a little on its own, so
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
one axis while the others keep moving, every 4.8 to 29 s; the loop starts and ends on the
same turning point, so it has no seam. The first pass glides in from wherever the ship is.
`drift_settle` (Hold steady) stops `drift` as it starts (a `stops` trigger) and eases the
three back to the middle over 6 s.

### Switching what the screens show

The three main monitors and the hologram each show a subscene (a scene placed as a
source, listed in the Scenes panel's `Monitor sources` folder), `src_left`, `src_center`, `src_right` and `src_holo`, which holds one item per
source it can show. `sources.py` builds them. Each has five, one per soft key under its
screen, left to right:

| Key | Item | Shows |
|---|---|---|
| 1 | `src_<screen>_transport` (`src_left_notes` on the left monitor) | the transport page (the left monitor: the notes page, the same as the far right side monitor's) |
| 2 | `src_<screen>_arrange` | the arrangement |
| 3 | `src_<screen>_device` | the device |
| 4 | `src_<screen>_mixer` | the mixer |
| 5 | `src_<screen>_feed` | a camera feed: the source `feed` (`holo_feed` on the hologram), a stand-in still until you point it elsewhere |

The left monitor starts on the notes, the centre on the arrangement, the right on the
device and the hologram on its feed. A screen shows whatever is visible in its subscene,
so you customise it as any scene: open "Centre monitor source" (`src_center`) from the Scenes panel's `Monitor sources`
folder and toggle its items'
visibility, point an item at a webcam, a capture or anything else (or send
`item.set_source`), or add, move, crop and layer items of your own.

A sequence a key, `<screen>_<slot>` ("Centre monitor: Mixer"), shows that key's item and
hides the subscene's other four (cues running `item.show` and `item.hide` at its start),
so the screen cuts to it. Items you added yourself are left as you set them. The sequence
also takes the screen's five channels, `src_<screen>_<slot>` (1 selected, 0 not), to that
key in `SOURCE_FADE_MS` (150 ms); they only light the soft keys, so showing or hiding an
item by hand doesn't move the lit key.
Play one from the app's sequences, a cue, an agent's `timeline.play`, or these (the notes follow the
views' and the cockpit sequences' notes, so they move up if those gain any):

| Screen | Keys (after Ctrl+Alt+Shift) | MIDI notes (with `NOTES=1`) |
|---|---|---|
| Left monitor | 1 to 5 | 58 to 62 |
| Centre monitor | 6 to 0 | 63 to 67 |
| Right monitor | Y, U, I, O, P | 68 to 72 |
| Hologram | Z, X, C, V, B | 73 to 77 |
| Desk (below) | N (pads), K (camera) | 78, 79 |

The selected source's key lights amber under its screen: the five soft keys under each
monitor, and a row of five on the dash just in front of and right of the hologram's
lens. Each key's face is a quad on the model's `screens` material that maps one block of
the atlas's key strip (the bottom 16 px of the readouts' space, under the LEDs; see the
model's README), and the atlas has a lit block a key
there, following its channel (the key last pressed, not what is visible). The keys are LEDs: the Glow and Master switches darken them
with the others, and the unlit keys go dark with the lights as the desk's pads do. `KEY_LIT` and `KEY_UNLIT` set the two colours. The opt-in glow cards (`GLOW_CARDS=1`) still
show each monitor's starting page, whatever its key picks, since a card glows only with a
source's own frame, not a scene's. It needs channels and
sequences (protocol 0.170); without them the screens show what they did before.

The desk's grid controller switches the same way: its subscene, `src_desk`, draws its
pads switched off (which dim with the lights) or a camera feed, `desk_feed`, over the whole 8:3 surface, which suits a camera
looking down on a long grid controller. Point `src_desk_feed` at the camera in the app, or toggle the subscene's items as on the monitors.
Ctrl+Alt+Shift+N shows the pads, Ctrl+Alt+Shift+K the camera (the sequences
`desk_grid` and `desk_feed`; MIDI notes 78 and 79). The desk has no soft keys to light.

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

## The Sound Journal title

The title card from Jeff's streams, over the live cockpit: the picture darkens, and the JMH shield and "Sound Journal" fade in, centred. `title.py` builds it and
`import_show.py` calls it.

![The cockpit under the Sound Journal title](title/title-on.jpg)

| | |
|---|---|
| In, out | Ctrl+Alt+J fades it in, Ctrl+Alt+Shift+J out, as do, with `NOTES=1`, notes `TITLE_NOTE` (84, C6) and 85 on channel 16. An agent sends `overlay.show` or `overlay.hide` on `sound_journal`, as `python3 title.py on` and `off` do |
| How long | the overlay's own fade, in and out |
| How it looks | the picture goes to `1 - TITLE_DIM` (0.38) of its brightness, as the card comes up to opaque |
| The card | `title/title.png`, drawn by `title/make_title.py`: the monogram over the words in Ubuntu Light (`title/Ubuntu-Light.ttf`, under the Ubuntu Font Licence in `title/UFL.txt`). The monogram is the font `Crepitus-monogram.ttf`'s ligature for `1jMh`; with that font in `title/`, the script draws it from the font, and without it, from a traced outline that stands in for it. `WORDS` changes the words |

The title is an overlay (JStream ADR-0210 decision 11): a 2D scene, `sound_journal`, put
over program, with a black card at `TITLE_DIM` (0.62) opacity over the whole canvas and the
title card above it. Program is never switched, so the view on screen, whichever of the
cockpit's keyframes it is, stays where it is under the title, and a view switched while
the title is up glides under it. The views, the lights, the warp and the hologram keep
working underneath, and the title works over any other scene too. An overlay can't blur
what is under it, so the picture only darkens. A sequence's cue can't put an overlay up
(JStream lets a cue run only switches, item, value, sequence and channel actions), so the
title has no channel: CC 45 and Mod 20 no longer drive it, only its keys and notes.

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
| What it shows | its subscene `src_holo`, which starts on the image source `holo_feed` (the 2D cockpit's caller still) and switches to the DAW pages on its keys ([Switching what the screens show](#switching-what-the-screens-show)). `python3 hologram.py source <source id>` points the feed slot at another source, such as a webcam or a screen capture made in the Sources panel, and selects it |
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

## Stress test

`stress.py` checks that JStream and the pages keep up with far more JTunnel data than a
normal session sends. It stands in for the JTunnel plugin (and the Bitwig extension behind it) on
127.0.0.1:47251, so JStream receives it with no change. Close Bitwig first, or take
JTunnel off its track, since only one program can hold the port. Then run:

    python stress.py              # a very heavy session at the extension's 30 ticks a second
    python stress.py --level 2    # twice that
    python stress.py --level 4    # far past anything Bitwig sends

What it sends:
- a 32 × 32 clip grid, every slot changing state every 0.5 to 2 s
- 8 tracks (`--automated`) whose volume and pan move every tick, so their whole `track/N` key goes each tick
- every meter, and up to 6 notes held on each track
- the device's controls, the mixer, the markers, scene launches and track selections
- tempo sweeps from 90 to 150 BPM, a transport stop every 45 s, and a loop jump back every 20 s
- the 32 modulation params, with Mods 1 to 25 moving every tick (`--mods 0` holds them, so the cockpit's warp and ship stay still)
- a 24-bit PCM stream carrying about 200 notes a second (`--audio midi` sends MIDI only, `--audio none` sends no audio stream)

It follows the plugin's state wire: what changed goes at once, and the whole state goes
again about once a second, a slice at a time, with each message's ID repeated. Every 5 s
it prints what it sent and how far it fell behind its own schedule. That way a slow
sender isn't mistaken for a slow receiver.

What to watch while it runs:
- JStream's `profile.get`: each page's paints a second, the program's fps, p95 and
  over-budget frames, and under `network` the input's `concealed` and `late` frames and
  `state_dropped`
- the CPU of the CEF processes (`jstream-browser-helper`)

A page's `?debug=1` prints its frames, draws and updates a second.

JStream before #1839 lost packets under this load, even at level 1. The OS drops a datagram
when the receive socket's buffer is full, and nothing counts it.

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
