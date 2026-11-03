# Cockpit build notes: what needed HTML, and what JStream could do natively

These are running notes from building the cockpit scene. They feed the end-of-build review.

- **Hotkeys can only switch scenes.** Every combination of state (location × effect)
  becomes its own variant. A hotkey action that shows or hides one item would remove
  most of them.
- **Continuous motion.** The cockpit sway, the drifting sky and the pulsing lights are
  done in HTML, because an item can't move continuously on its own. Native candidates:
  a "wiggle" or noise modifier on an item's transform, and a looping keyframe track.
- **A shared clock.** The pages stay in step by using the wall clock (`Date.now`), so
  the sky, the reflections and the cockpit agree. A native animation clock would need
  the same property.
- **Reflections should be native.** In round 3 each page drew its own reflection, and
  that broke when layers stacked: during a warp-out, the destination sky under the warp
  already reflected its stars on the dash. A reflection has to mirror the composite you
  actually see, which only the compositor has. JStream can already do this:
  - a `scene` source of the outside layers, placed with `flip_v` and a squashed height;
  - `blur` and `image_mask` (a specific gloss mask) on that source's chain, which
    draws since #1036;
  - an `additive` blend.

  A second one mirrors the monitors and holograms into the glass. Round 4 simulates
  exactly that stack in `demo.html` (`refl.js`). What's missing natively is only the
  sway: masks and mirrors would need to follow the cockpit's continuous motion.
- **Audio reactivity.** It's simulated in the pages. Native candidate: JStream sends
  audio levels or bands to browser sources, or filter parameters follow a meter.
- **Keying the plate.** The `chroma_key` filter can do this natively. HTML only needed
  it because the cockpit moves inside the page.
- **Shaders.** WGSL effect packs exist (ADR-0035). An effect is one fullscreen pass that
  becomes a `video_filter` kind, with live parameters and `frame.time`. The gaps:
  - one pass, with no feedback from the previous frame;
  - no extra textures or bindings;
  - no audio input;
  - packs load from a folder on disk, so an agent can't author one over MCP.

  Native candidate: a shader *source*, plus a way for MCP to write packs. Jeff asked for
  this to go on the list.
- **Masks.** The native `image_mask` and `scene_mask` filters (luma or alpha) exist,
  and items can be flipped and blurred, so the reflections above are native-ready.
  Make the masks specific: a few glossy surfaces with a fresnel ramp, never one broad
  sheen over the whole cockpit, which reads as generic.
