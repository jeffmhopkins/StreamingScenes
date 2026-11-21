# 3D cockpit model

A starship flight deck as a real 3D model, for JStream's `model` source (ADR-0107):
glTF 2.0, metallic-roughness materials, five 16:9 screens and a desk instrument that are
each their own material so a live source can be mapped onto any of them. It is meant for camera moves
and depth of field inside the cockpit, close enough to read the readouts.

The look follows the green-screen plate of [starship-cockpit](../starship-cockpit/)
and the "used future" of working-ship sets: dark gunmetal paint with grime and scratches,
a strutted canopy (one big raked windshield, corner panes, side windows and glass roof
panels over the pilot), and every console covered in
greebled sub-panels, amber readouts, button banks, switches, knobs and vents, with cable
looms and conduits on the roof. There is no seat, so the camera can sit where a pilot
would. On a desk in front of the monitors lies a grid instrument that looks switched
off until a live source is put on it.

![The cockpit from the back of the cabin](media/overview.jpg)

| | |
|---|---|
| ![The pilot's view](media/pilot.jpg) | ![Through the windshield](media/windshield.jpg) |
| ![The desk instrument, switched off](media/desk.jpg) | ![The canopy from the side](media/canopy.jpg) |
| ![The left console](media/left-console.jpg) | ![The dashboard up close](media/dash-closeup.jpg) |

![A macro shot of the dashboard buttons: the texture stays sharp](media/button-macro.jpg)

The stills are Blender Cycles renders of the same geometry and textures, lit with two area
lights, the model's own light strips and LEDs, and a starfield behind the glass. JStream lights the model with its own rig or the
scene's lights, so it will not look exactly like this there.

## Files

| Path | What it is |
|---|---|
| [`model/cockpit.gltf`](model/cockpit.gltf) | The model. Point a `model` source's `file` at it. Its `cockpit.bin` and `textures/` must stay beside it. |
| [`model/throttle.gltf`](model/throttle.gltf) | The throttle lever by itself, so a scene can move it. It uses the same `textures/`. See [The throttle lever](#the-throttle-lever). |
| [`model/textures/`](model/textures/) | 23 images: five tiling PBR sets (colour, normal, occlusion-roughness-metalness), the decal atlas, the amber readout atlas, and a placeholder card per screen. |
| [`model/CREDITS.md`](model/CREDITS.md) | Where every texture comes from, and its licence (all CC0). |
| [`tools/make_textures.py`](tools/make_textures.py) | Builds `textures/` from the ambientCG downloads (baking the grime and scratches into the paint set), and draws the decals, readouts and screen cards. |
| [`tools/build_cockpit.py`](tools/build_cockpit.py) | Builds the model in Blender from code and exports it. |
| [`tools/finish_gltf.py`](tools/finish_gltf.py) | Wires the textures into the exported glTF. |
| [`tools/render_previews.py`](tools/render_previews.py) | Renders the stills above. |

## Numbers

Checked by loading the file with JStream's own glTF loader (`jstream-sources`), with its
real image decoders:

| | This model | JStream's cap |
|---|---|---|
| Triangles | 364,708 | 2,000,000 |
| Textures | 23, all 2048 px or smaller | 64, 4096 px a side |
| Memory | 380 MiB of textures with mips, 34 MiB of mesh: 414 MiB | 512 MiB |
| Extensions | `KHR_materials_unlit`, `KHR_materials_emissive_strength` | both read |
| Compression | none (no Draco, meshopt or KTX2) | none read |

Nothing in the file was reported as ignored. `throttle.gltf` loads the same way: 408
triangles, and its own copy of the `paint` and `plastic` sets, 128 MiB.

## Why it stays sharp up close

No surface has one unique texture stretched over it. Every surface uses one of five
tiling 2048 px texture sets, with texture coordinates projected from world position in
metres, so the detail per metre is the same everywhere and doesn't depend on how big a
part is:

| Set | Used for | Repeats every | Texels per cm |
|---|---|---|---|
| `paint` | walls, consoles, ceiling, frames; gunmetal with baked grime, mottling and scratches (`paint_dark` is the same set darkened) | 50 cm | 41 |
| `floor` | the deck | 60 cm | 34 |
| `leather` | stick boots, some cable looms | 30 cm | 68 |
| `plastic` | bezels, buttons, grips, trim | 40 cm | 51 |
| `hexpanel` | vents, hatch, roof and wall insets | 50 cm | 41 |

A 2 cm button fills a 1080p frame at a ~5 cm field of view and still has about 100 texels
across it. Bevels, bolts, buttons and switches are real geometry, not normal-map detail,
so their edges stay sharp at any distance. Labels and stripes come from one 2048 px decal
atlas, at 3 to 6 texels per mm on the panels that carry them. Each amber readout is one
256 × 128 px cell of the readout atlas on a display 4 to 25 cm wide.

## Layout

The model is in metres, glTF axes: **+x right, +y up, +z toward the back of the cabin**.
The pilot faces **−z**, toward the windshield. The deck is at y = 0. In JStream's model
source, glTF +z is toward the viewer, so the default view looks from the back of the
cabin toward the windshield.

| Part (node) | Where |
|---|---|
| Whole cabin | x −1.40 to 1.40, y 0 to 2.20, z −2.02 (windshield base) to 1.76 (rear bulkhead) |
| Pilot's eye point | about (0, 1.22, 0.45), looking toward −z |
| `windshield` | the canopy forward of the side windows. One raked windshield: its base at y 1.16, z −2.45, x ±0.86; its top at the roof, y 2.16, z −1.50, x ±0.62. A corner pane each side joins it to the side windows at z −1.25. Thin struts frame every edge. Also the glareshield at the sill and the square hull below it. |
| Side windows (in `cabin`) | glass on both walls from the console sill (y 0.85) to the roof (y 2.16), from z 0.15 forward to z −1.25, split by a rib at z −0.62 and a transom at y 1.65. The roof's outer panels between z −0.62 and −1.25 are glass too. |
| `header` | the lit, greebled header under the roof behind the top of the windshield |
| `dashboard` | across the front, under the canopy; top at y ≈ 0.67; greebled banks between the lip and the screens; the desk, reaching back to z −0.42 at y ≈ 0.55 to 0.68, on two arms |
| `side_consoles` | either side, x ±0.62 to ±1.35, z −1.18 to 0.75; the throttle's base and slot on the left (the lever is `throttle.gltf`), side stick on the right; greebled tops and inner faces |
| `conduits` | cable looms along the roof edges and down the pillars, roof conduits, greebled roof and rear-wall panels |
| `rear_bulkhead` | the back wall, with a hatch |
| `cabin` | walls, ribs, roof with light strips, floor, pipes, the side windows |

All glass is the one `glass` material (alpha-blended, nearly clear): whatever is behind the
model in the scene shows through every window. There is no seat and no centre
console; the floor from the desk back (x ±0.6, z −0.4 to 1.6) is clear for the camera.

### Screens

Each screen is its own node **and** its own material, with the same name. Its texture
coordinates cover the whole image once, with the image's top-left at the screen's
top-left as the pilot sees it, at 16:9, so a 1920 × 1080 source maps without stretching.
Screen materials are `KHR_materials_unlit`: a source on a screen shows at its own colours,
like a display, whatever the lighting. Until a live source replaces one, it shows a test
card with its name.

| Material / node | Size (m) | Top-left | Top-right | Bottom-left | Bottom-right | Faces |
|---|---|---|---|---|---|---|
| `screen_center` | 0.720 × 0.405 | (−0.360, 1.136, −1.489) | (0.360, 1.136, −1.489) | (−0.360, 0.744, −1.391) | (0.360, 0.744, −1.391) | (0, 0.24, 0.97) |
| `screen_left` | 0.500 × 0.281 | (−0.894, 1.036, −1.264) | (−0.461, 1.036, −1.514) | (−0.859, 0.764, −1.206) | (−0.426, 0.764, −1.456) | (0.49, 0.24, 0.84) |
| `screen_right` | 0.500 × 0.281 | (0.461, 1.036, −1.514) | (0.894, 1.036, −1.264) | (0.426, 0.764, −1.456) | (0.859, 0.764, −1.206) | (−0.49, 0.24, 0.84) |
| `screen_side_left` | 0.300 × 0.169 | (−1.114, 0.914, −0.767) | (−0.955, 0.914, −1.021) | (−1.005, 0.806, −0.699) | (−0.846, 0.806, −0.953) | (0.55, 0.77, 0.34) |
| `screen_side_right` | 0.300 × 0.169 | (0.955, 0.914, −1.021) | (1.114, 0.914, −0.767) | (0.846, 0.806, −0.953) | (1.005, 0.806, −0.699) | (−0.55, 0.77, 0.34) |
| `screen_desk` | 0.720 × 0.270 (8:3) | (−0.360, 0.688, −0.832) | (0.360, 0.688, −0.832) | (−0.360, 0.632, −0.568) | (0.360, 0.632, −0.568) | (0, 0.98, 0.21) |

`screen_desk` is the playing surface of the instrument on the desk. It is the one screen
that is not 16:9: it is 8:3, the shape of a long grid controller seen from above, so crop
the source to the instrument. Its placeholder is a dark 24 × 8 grid of pads, so the
instrument reads as switched off until a live source (a top-down camera on the real
instrument, say) replaces it. To switch it off again, take the source off the material:
ADR-0107 says a named source that isn't drawing reads transparent, not as the placeholder.

To put a live source on a screen, give the model source `texture` = that source and
`texture_material` = the screen's material name (ADR-0107 decision 5). Where a model
source can't do that yet, a flat card placed on the corners above does the same job.

### The throttle lever

JStream can't move one node inside a model, so the lever (shaft and grip) is not in
`cockpit.gltf`. It is `throttle.gltf`, a second model to place in the scene, with its
origin at the hinge inside the base. It is modelled upright, at the middle of its travel.

| | |
|---|---|
| Hinge (pivot), in the cockpit's coordinates | (−0.950, 0.721, 0.100) |
| Hinge axis | the cockpit's x axis: the grip swings toward −z (forward) or +z (back) |
| Travel | −25° to +25° from upright; the slot in the base is 24 cm long |
| Size | 0.120 × 0.220 × 0.080 m (x, y, z) |
| Bounds centre, from the pivot | (0, 0.110, 0): the lever stands on its pivot |

To animate it, put the lever in a group whose centre is the pivot, offset the lever by
its bounds centre, and tilt the group.

### All materials

`paint`, `paint_dark`, `floor`, `leather`, `plastic`, `hexpanel` (tiling PBR sets),
`glass` (blended), `decals` (alpha-masked labels and stripes), `readout` (the amber
displays, emissive from the readout atlas), `light_strip` and `led_amber`, `led_red`,
`led_green`, `led_blue` (emissive), and the six `screen_*` materials above.

## Rebuilding it

```sh
pip install bpy pillow numpy        # Blender as a Python module (5.x), and Pillow
# Download the 2K-JPG zip of each ambientCG asset in model/CREDITS.md and unpack each
# into its own folder named after the asset, under dl/.
python tools/make_textures.py dl model/textures
python tools/build_cockpit.py model/textures model/cockpit.gltf --blend cockpit.blend
python tools/finish_gltf.py model/cockpit.gltf
python tools/render_previews.py cockpit.blend media 48 1280
```

`build_cockpit.py` is plain code: boxes, extruded profiles and cylinders, bevelled, then
joined into one node per part. Change a dimension there and rebuild; the screen table
above comes from the `SCREENS` table at its top.
