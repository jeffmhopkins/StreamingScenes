# Streaming scenes

Scenes for Jeff's live streams, built for [JStream](https://github.com/jeffmhopkins/JStream).
Each folder holds a complete scene: its pages and art, the scripts that made the art, how to
set it up in JStream, and demo videos and stills.

| Scene | What it is |
|---|---|
| [starship-cockpit](starship-cockpit/) | A photoreal starship cockpit with live cameras on its monitors. It can warp between three locations, fight off an asteroid, take fire, receive a hologram transmission, and raise a hologram of the Bitwig session. The music drives its lights. |
| [cockpit-3d](cockpit-3d/) | A weathered starship flight deck as a glTF 3D model for JStream's model source: a wide panoramic windshield, three hooded monitors wrapped around the pilot, an overhead console, dense amber-lit consoles, tiling CC0 PBR textures that stay sharp up close, seven 16:9 screens and a desk instrument that take live sources. |
| [feature-tour](feature-tour/) | A show that tours what JStream does: screenshots of the app with camera moves and callouts, a live broadcast scene built from Tears of Steel stills, keyframes, motion modifiers and the 3D cockpit, with a readable script on every bookmark. |
| [camera-demos](camera-demos/) | Three clips of JStream's 3D scene camera: a depth-of-field focus pull, a gliding close-up of the JStream UI, and the follow camera chasing the pointer over it. |

## The demo project

[`jstream-demos.json`](jstream-demos.json) is one JStream project with the
[feature tour](feature-tour/) and the [DAW cockpit](cockpit-3d/daw/) in it, and three shows:

| Show | What it is |
|---|---|
| Feature tour | The tour of JStream, 16 chapters with a script in every bookmark. |
| Cockpit tour | A walk through the DAW cockpit: power up, the seat, the desk, the monitors, the consoles, warp, the hologram, the 2D desk and power down. |
| Lightning tour (no pauses) | The title, Keyframes, the 3D cockpit stills and Thanks, looping. |

Open it from a checkout of this repo (**File › Open project…**): its pictures, fonts and the
cockpit's model are found by their paths from the root. It needs a JStream with scene folders
(protocol 0.190, the alpha.13 train), where the cockpit's views are keyframes in a `Views`
folder under it. The cockpit's screens follow Bitwig once the app receives from
Bitwig's JTunnel sender, whatever its name: the project names no input, so it reads the
live sender ([its README](cockpit-3d/daw/README.md#importing-the-show)).

Bitwig: the cockpit is built with every Bitwig input its import offers, all on MIDI
channel 16, from whichever JTunnel sender is live:
- the live data on its screens, readouts, desk lights and LEDs
- the light switches (CCs 40 to 44) and the ship (CCs 30 to 33)
- the camera CCs 20 to 29, which also give each view its depth of field and autofocus
- notes from 36 up that switch the views and play the cockpit's sequences
- the JTunnel Mods

See [its README](cockpit-3d/daw/README.md#what-follows-the-data). The tour's MIDI pads
(notes 36 to 39) listen on channel 1, so they don't answer those notes.

Keys: the tour's keys are in [its README](feature-tour/README.md#run-it). The cockpit's are as
[its README](cockpit-3d/daw/README.md#importing-the-show) gives them, except its camera views, which are on
Ctrl+Shift+1 to 0, - and = here, since the tour's Go to keys hold Ctrl+Alt+1 to 8 and 0.

To rebuild it after changing either part:

1. `python3 tools/build_demos.py` writes `build/tour.json` and `build/cockpit-edits.json`:
   the tour, and every edit `cockpit-3d/daw/import_show.py` makes, recorded without an app.
2. Copy `tools/bake_demos.rs` into a JStream checkout as
   `crates/jstream-graph/tests/bake_demos.rs` and run
   `DEMOS=<this repo> cargo test -p jstream-graph --test bake_demos`. It applies the edits
   with JStream's own code and writes `jstream-demos.json` in the form JStream saves.
