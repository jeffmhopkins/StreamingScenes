# Starship cockpit

A photoreal starship cockpit for live streams. Your cameras play on its monitors, which can
also show radar, engineering, an audio spectrum, navigation or shields. Through the windows
is real-looking space, at one of three locations. On demand the ship can:

- **warp** from one location to another;
- **fire on an asteroid** and blow it up;
- **take fire**;
- **receive a transmission**, a caller shown as a hologram;
- **raise a hologram of the Bitwig session**.

The cockpit sways slightly, as if you were sitting in it. Its amber lights pulse with the
music. The space outside reflects in its glossy surfaces and lights them: hyperspace blue,
a laser flash, the orange of an explosion.

![The cockpit at the Kestrel Nebula](media/nebula.jpg)

## Demo

[`media/cockpit-demo.mp4`](media/cockpit-demo.mp4) runs through every effect in under a
minute. It was rendered in Chromium, from these same pages stacked as the JStream scene
stacks them and switched on the hotkey timeline.

[`media/cockpit-jstream.mp4`](media/cockpit-jstream.mp4) is the same timeline running in
JStream itself on Linux, recorded with JStream's own `record` output. See
[In JStream](#in-jstream) for how it was built and how it differs.

The camera monitors show stills from Jeff's January stream. The hologram caller is a still
from his May stream, and the Bitwig hologram is a crop of the January stream's Bitwig
screen. All of them stand in for live sources.

## How it's built

Every moving part is an HTML page shown in a JStream `browser` source. All the pages use one
clock, the wall clock (`Date.now`), so separate sources stay in step without talking to
each other. That clock drives:

- the cockpit's sway;
- the ship's drift against the sky;
- the music the lights follow;
- the windows' mask.

`pages/ship.js` holds what they share:

- the clock, the sway and the ship's attitude;
- the simulated music;
- `Outside`, the compositor every outside layer draws through.

`Outside` masks a layer to the windows, which move with the sway, then draws the light
the layer throws into the cockpit.

**Reflections** are one layer, not each page's own (`pages/refl.js`, masks from
`tools/masks2.py`). Round 3 had every outside page reflect itself. So while a warp-out
still covered the window, the destination sky under it was already reflecting its stars
on the dash. Now one layer mirrors the composite that actually shows through the glass,
whatever is stacked there, onto three specific masks. In the still below, a warp-out still covers
the window, and the dash reflects only the warp:

![Mid warp-out: the dash reflects the warp, not the sky behind it](media/warp-out-reflection.jpg)


- `m-ledge.png`, `m-sill.png` and `m-seat.png`: the console under the monitors, the
  side sills and the seat bolsters. Each mirrors the glass from its own top edge, with
  a fresnel ramp. The masks come from the plate's own lighting (`tools/masks3.py`): the
  plate was lit from the windows, so the faces and specular lips that already catch
  that light are the ones that face the glass. A reflection then follows the real
  panels and edges. Drawn shapes, which round 4 used, read as slabs pasted on top.
- `m-edge.png`: the window frame bevels. The outside is blurred so it bleeds onto them as
  rim light, which is what flashes, lasers and explosions catch.
- `m-glass.png`: the glass itself. It faintly ghosts the lit interior, meaning the
  monitors and the holograms, mirrored about the window's lower edge.

In the demo, `demo.html` reads the shown pages' canvases to build it. In JStream it maps
to native parts: a `scene` source of the outside layers placed with `flip_v` and a
squashed scale, with `blur` and `image_mask` on the source's chain (drawn since #1036),
and an `additive` blend. A second one does the same for the monitors and holograms.

**Music.** It's simulated for now: 118 BPM, with a kick, snare, hats, bass and pad, and a
4-bar breakdown every 16 bars. When JStream can give a page audio levels, `audio(s)` in
`ship.js` is the one function to replace.

### Layers, bottom to top

All are 1920 × 1080, placed full-frame, unless the table says otherwise. A **Restart**
layer has `restart_on_show` on and starts hidden. Layers 1 to 3 and the caller sit under
the cockpit; everything else draws over it.

| # | Layer | Source | Restart | Notes |
|---|---|---|---|---|
| 1 | Black | `color` #000 | | |
| 2 | Monitors 1 to 3 | your cameras | | Placed 8 px larger than the screens, so the sway never shows an edge: (482, 523, 345 × 184), (835, 523, 333 × 183), (1174, 523, 342 × 184). |
| 3 | Monitor pictures | `screen-*.html`, 690 × 368 each | yes | Placed in the same boxes as layer 2. `screen-camhud-N` frames a camera; `radar`, `telemetry`, `spectrum`, `nav` and `shields` replace it. Each powers on like a CRT when shown. |
| 4 | Cockpit | `cockpit.html` | | The keyed cockpit, its sway, and its music-driven lights. |
| 5 | Sky | `sky-deep.html`, `sky-nebula.html`, `sky-planet.html` | | One shown per location. |
| 6 | Warp | `warp-in-<from>.html`, `warp-out-<to>.html` | yes | `warp-in` covers the windows with hyperspace. `warp-out` drops into its location's sky and, once it ends, matches the sky page exactly. |
| 7 | Weapons | `attack.html` | yes | About 7 s: lock-on, four laser volleys, the explosion. Clears itself. |
| 8 | Caller | the caller's camera at (700, 130, 520 × 292) | | Blend **screen**, opacity 75%. A **color correction** filter with saturation -1 and multiply `#78dcff`. Fades in after 1700 ms. |
| 9 | Bitwig | a window capture of Bitwig at (600, 84, 720 × 405) | | The same blend and filter as the caller. Fades in after 1100 ms. |
| 10 | Taking fire | `hit.html` | yes | Emergency lighting and smoke stay on until it's hidden. |
| 11 | Transmission | `transmission.html` | yes | |
| 12 | Bitwig frame | `bitwig.html` | yes | |

The pages read their images from beside them with `getImageData`, so serve `pages/` over
http and load them with `url`; from `file` their canvases are tainted. The
art is in `pages/`:

- `cockpit.png`, Jeff's green-screen cockpit plate with the green keyed out;
- the three sky plates (`stars.jpg`, `nebula.jpg`, `planet.jpg`);
- the masks (`m-window.png`, `m-gloss.png`, `lights.png`);
- `rock.png` and `debris.png`, the asteroid and its pieces.

### Variants and hotkeys

JStream hotkeys can only switch scenes, so each combination of location and effect is a
keyframe variant of the cockpit scene. Each one shows the layers it needs:

- **At each location:** Cruise, Weapons, Taking fire, Transmission and Bitwig. Each shows
  that location's sky and its `warp-out` page. `warp-out` stays shown, so returning to
  Cruise doesn't play the drop out again.
- **Warp from each location:** shows `warp-in-<from>` over the old sky.
- **Arriving:** switching from a Warp variant to a location's Cruise shows its
  `warp-out-<to>`, which plays the drop out.
- **Monitor sets** are more variants (Cams, Scan, Nav), or a nested scene per monitor whose
  variants pick its picture.

The demo uses these keys: F1 Cruise, F2 Warp, F3 Arrive, F4 Taking fire, F5 Transmission,
F6 and F7 monitor sets, F8 Weapons, F9 Bitwig. With three locations, a Stream Deck page per
location is easier than one hotkey per variant.

## Tools

- `tools/` holds the Python that made the art:
  - `common.py`, `plate.py`, `nebula.py` and `planet.py` make the sky plates;
  - `rock.py` makes the asteroid and debris;
  - `masks.py` makes the window, gloss and light masks from `cockpit.png`.
- `tools/rec.js` and `tools/vt.js` record the demo with Playwright on a virtual clock,
  frame by frame, and `tools/quick.js` renders one still.
  - `pages/demo.html` stacks the layers as the scene does.
  - The `cam*.png`, `caller_holo.png` and `daw_holo.png` stand-ins sit beside it.
  - To record, serve `pages/` with `python3 -m http.server 8767`, then run
    `node tools/rec.js` from `pages/`. It writes frames to `f/`.

## In JStream

`jstream/` builds the scene in a running JStream daemon over MCP and plays the timeline:

- `build_cockpit.py` creates the sources, groups, filters and the 11 keyframe variants
  that `tools/rec.js` steps through, plus an `hq` encoder profile (VBR 20 Mbps).
- `drive.py` switches variants on the timeline, as the hotkeys would, sets the key label,
  and records to an mp4.
- `mcp.py` is the small MCP client they share. `collection-state.json` is a `state.get`
  export of the built collection.
- `slowserve.py` serves `pages/` with an optional slowed clock (below).

Run the daemon, serve `pages/` with `python3 slowserve.py <pages>` on port 8767 under a
hostname (the scripts use `cockpit.test`, mapped to 127.0.0.1 in `/etc/hosts`), and run
`build_cockpit.py`, then `drive.py`. `JS_TOKEN` names the daemon's token file.

![Arriving at the Kestrel Nebula, composited by JStream](media/jstream-nebula.jpg)

The reflections are fully native, as the notes above suggest:

- **Console:** for each of the ledge, the sills and the seat bolsters, a group holds the
  outside as a `scene` source, flipped with `flip_v` and squashed so its mirror line lands
  on the surface's top edge. It has a `blur` on the item, and an `image_mask` with that
  surface's mask on the group's source. It's placed with an `additive` blend.
- **Edge:** the outside again, unflipped, more blurred, masked with `m-edge`, additive.
- **Glass:** the monitors, holograms and overlays mirrored about the window's lower edge,
  masked with `m-glass`, additive at 8%.

How the JStream version differs from the Chromium demo:

- **It was captured in slow motion.** The test machine had no GPU, so JStream composited
  on the lavapipe software rasterizer, at about 0.4 frames a second with every blur and
  mask on. So `slowserve.py` slows the pages' clock 110 times (`Date.now`,
  `performance.now` and the animation-frame time), `drive.py` stretches the timeline to
  match, and the recording was retimed to 30 fps with
  `ffmpeg -vf "setpts=(PTS-STARTPTS)/110,fps=30"`. Every frame is a real JStream composite;
  on a machine with a GPU the scene runs at real speed with `SLOW` unset.
- **One sway moves every layer.** The pages run with `?sway=0` (read by `ship.js`), and
  `drive.py` moves the plate, the outside, the monitors, the holograms, the overlays and
  the reflections together with the sway of `ship.js` and the knock of `rec.js`, so nothing
  slips against its bezel. The gloss masks move with their reflections.
- **Veils and reflections blend like a browser.** The pages with translucent light (the
  outside with its spill, the overlays, the camera frames) use JStream's `normal_srgb`,
  and the reflections `additive_srgb` at about the gains of `refl.js` (ledge 2.2, sill 2.0,
  seat 1.7, edge 3.2, glass 0.2; take 9 used 1.8 and 1.4 for the first two), with its blurs scaled to full size
  ([#1109](https://github.com/jeffmhopkins/JStream/pull/1109),
  [#1104](https://github.com/jeffmhopkins/JStream/pull/1104)). With plain `normal`, which
  blends in linear light, set `SPILL=0.4` or the spill washes out the cockpit.
- **Each arrival holds the warp-in under the warp-out** for 600 ms, since a page that is
  shown reloads and is transparent until it paints.
- **The hologram fades are stepped over MCP** in a slowed capture, since item transitions
  run on real time. At real speed `build_cockpit.py` uses item transitions instead.
- **The monitors and holograms sway and jolt through MCP.** In the demo they sit inside
  the swaying page. Here they are native items, so `drive.py` computes the same sway and
  the taking-fire knock as `ship.js` and `rec.js`, and sends each frame's placement with
  `item.set_geometry` ([#1058](https://github.com/jeffmhopkins/JStream/issues/1058) would
  make that native).
- **The glass cracks are clipped to the window.** `hit.html` masks its cracked canopy with
  `m-window.png` under the same sway, so the cracks never cross the frame.
- **No audio**: the record output carries the daemon's silent mix.
- **Pages load over http from a hostname.** On Linux, a browser source refuses a local
  `http://127.0.0.1` URL ([#1069](https://github.com/jeffmhopkins/JStream/issues/1069)), and from `file` the pages can't read their own images.

The gaps it found are JStream issues [#1069](https://github.com/jeffmhopkins/JStream/issues/1069) to
[#1073](https://github.com/jeffmhopkins/JStream/issues/1073): local URLs refused on Linux, software
compositing too slow for nested scenes with blur and masks, hidden browser sources that
keep painting, a recording path that can't be changed or overwrite a file, and no hint to
install a Vulkan driver when there's no adapter.

## What this scene taught us about JStream

These notes feed the review of what should be native and what should stay in HTML:

- **Hotkeys only switch scenes.** Location × effect turns into dozens of variants. A hotkey
  action that shows or hides one item would remove most of them.
- **Nothing moves continuously.** The sway, the drift and the pulsing lights had to be
  HTML. A native noise or wiggle on an item's transform, and looping keyframe tracks, would
  cover them.
- **A page can't see other sources.** So per-page reflections went wrong whenever layers
  stacked (round 3's warp-out bug). Reflections belong native: a `scene` source of what
  they mirror, with `flip_v`, `blur`, `image_mask` and an `additive` blend, all of which
  exist now.
- **Shaders:**
  - The warp, the tunnel, the zoom blur and the fireball belong in a native shader source,
    with multipass, feedback, textures and audio.
  - WGSL effect packs exist today, but only as single-pass filters, and an agent can't
    write one over MCP.
- **Audio** has to be simulated: pages can't hear the mix.
