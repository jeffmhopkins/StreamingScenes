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
- **Reflections need the source picture.** A page can't read another source, so each
  page draws its own reflection. Native candidates: an item that mirrors another source
  (flip, blur, masked by an image's luminance, screen blend), or a "mask from image"
  filter.
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
- **Masks.** The native `image_mask` and `scene_mask` filters (luma or alpha) exist, so
  a reflection could be done natively from a scene that mirrors the sky, if items could
  be flipped and blurred.
