"""Builds the 3D cockpit scene in a running JStream daemon over MCP.

One 3D scene, `cockpit`, holds the cockpit model, a space plate far past the
windshield, the scene's lights and its depth-aware filters. A 2D scene, `feed`, is the
live picture on the centre monitor, mapped onto the model's `screen_center` material
through the model's `texture` setting. Four keyframe variants of `cockpit` hold the
camera shots the demo glides between; a `move` preset glides the camera, its focus and
its blur.

JS_TOKEN names the daemon's token file and JS_MCP its endpoint, as for mcp.py.
SLOW=F stretches the glide and the feed's motion F times, for a slowed capture
(drive.py); unset, everything runs at real speed.
"""
import os
import sys

from mcp import init, op, batch, asset
from shots import BACK, BOUNDS_MAX, BOUNDS_MIN, CX, CY, MODEL, S, SHOTS, THROTTLE_PIVOT, _bounds, p

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PAGES = os.path.join(ROOT, "starship-cockpit", "pages")
F = float(os.environ.get("SLOW", "1"))
# PAGES_URL serves starship-cockpit/pages (its slowserve.py): the 2D cockpit's own space
# and warp pages then fill the windows, on a card far past the windshield.
PAGES_URL = os.environ.get("PAGES_URL", "")


def geo(cx, cy, w, h, **kw):
    g = {"center": {"x": cx, "y": cy}, "size": {"width": w, "height": h}}
    g.update(kw)
    return g


def src(sid, name, kind, settings):
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": kind}, "settings": settings}


def add(scene, item, source, g, **kw):
    e = {"type": "item.add", "scene_id": scene, "item_id": item, "source_id": source,
         "geometry": g}
    e.update(kw)
    return e


def flt(owner, fid, kind, settings):
    return {"type": "filter.add", "owner": owner, "chain": "video", "filter_id": fid,
            "kind": kind, "settings": settings}


def must(result, what):
    text, ok = result
    if not ok:
        sys.exit(f"{what} failed")
    return text


init()
must(op({"type": "canvas.set_size", "width": 1920, "height": 1080}), "canvas")

# ---- the live feed: a 2D scene, shown on the centre monitor ----
must(batch([
    {"type": "scene.create", "scene_id": "feed", "name": "Monitor feed"},
    src("feed_cam", "Crew camera (stand-in)", "image", {"file": asset(f"{PAGES}/cam2.png")}),
    src("feed_bg", "Feed background", "color", {"color": "#05121cff", "width": 1920, "height": 1080}),
    src("feed_bar", "Scan bar", "shape", {"width": 1920, "height": 10, "color": "#5fe3ff80"}),
    src("feed_tag", "Feed tag", "text", {"text": "CAM 2  ·  LIVE", "size": 64, "face": "condensed_bold",
                                         "color": "#ffffffff", "background": "#c0182acc", "padding": 18}),
    add("feed", "bg", "feed_bg", geo(960, 540, 1920, 1080)),
    add("feed", "cam", "feed_cam", geo(960, 540, 1920, 1080, fit_mode="fill")),
    add("feed", "bar", "feed_bar", geo(960, 540, 1920, 10)),
    add("feed", "tag", "feed_tag", geo(300, 110, 480, 110)),
], "feed"), "feed")
# The scan bar sweeps the picture, so the monitor visibly shows a live picture.
must(op({"type": "item.set_motion", "scene_id": "feed", "item_id": "bar", "motion": [
    {"modifier_id": "sweep", "property": "y", "enabled": True, "clock": "engine",
     "kind": "oscillate", "shape": "triangle", "amplitude": 520.0,
     "period_ms": int(4000 * F), "phase": 0.0}]}), "feed motion")

# The feed scene as a source, for the model's texture.
must(op({"type": "source.create", "source_id": "feed_src", "name": "Monitor feed",
         "kind": {"type": "scene", "scene_id": "feed"}}),
     "feed source")

# ---- the cockpit: a 3D scene ----
cam = SHOTS["cockpit"]
must(batch([
    {"type": "scene.create", "scene_id": "cockpit", "name": "3D cockpit"},
    *([src("space", "Space", "browser", {"url": f"{PAGES_URL}/sky-deep.html?sway=0&layer=sky",
                                         "width": 1920, "height": 1080, "fps": 30}),
       src("warp_page", "Warp", "browser", {"url": f"{PAGES_URL}/warp-in-deep.html?sway=0&layer=sky",
                                            "width": 1920, "height": 1080, "fps": 30,
                                            "restart_on_show": True})]
      if PAGES_URL else [src("space", "Space", "image", {"file": asset(f"{PAGES}/planet.jpg")})]),
    src("cockpit_model", "Cockpit", "model", {
        "file": asset(MODEL), "lighting": "scene",
        "texture": {"type": "source", "source_id": "feed_src"}, "texture_material": "screen_center"}),
], "cockpit sources"), "cockpit sources")

# With PAGES_URL, the 2D cockpit's space and warp pages make one 2D scene, `outside`:
# it fills the windows (on the plate below) and is the environment light's sky, so the
# cockpit reflects and is lit by what is outside, the warp included.
if PAGES_URL:
    must(batch([
        {"type": "scene.create", "scene_id": "outside", "name": "Outside", "role": "group"},
        add("outside", "sky", "space", geo(960, 540, 1920, 1080)),
        add("outside", "warp", "warp_page", geo(960, 540, 1920, 1080)),
        {"type": "item.set_visible", "item_id": "warp", "visible": False},
        {"type": "source.create", "source_id": "outside_src", "name": "Outside",
         "kind": {"type": "scene", "scene_id": "outside"}},
    ], "outside"), "outside")
    # The warp as a keyframe of `outside` (scene.set_keyframe at the jump): a variant of
    # `cockpit` can't reach into it through the far card.
    must(batch([
        {"type": "scene.create_variant", "scene_id": "outside_warp", "variant_of": "outside",
         "name": "Outside · warp"},
        {"type": "item.set_visible", "scene_id": "outside_warp", "item_id": "sky", "visible": False},
        {"type": "item.set_visible", "scene_id": "outside_warp", "item_id": "warp", "visible": True},
    ], "outside warp"), "outside warp")

# The plate: 40 m past the windshield, big enough to fill any shot through it.
far_z = -40.0
plate_w = 64000
must(batch([
    {"type": "scene.set_camera", "scene_id": "cockpit", "camera": cam},
    add("cockpit", "space", "outside_src" if PAGES_URL else "space",
        geo(p(0, 6.0, 0)["x"], p(0, 6.0, 0)["y"], plate_w, plate_w * 9 / 16,
            depth_px=p(0, 0, far_z)["z"], fit_mode="stretch")),
    add("cockpit", "model", "cockpit_model",
        geo(CX, CY, S * (BOUNDS_MAX[0] - BOUNDS_MIN[0]), S * (BOUNDS_MAX[1] - BOUNDS_MIN[1]),
            depth_px=0.0)),
], "cockpit items"), "cockpit items")

# The throttle lever, where the model ships one: a second model placed at its hinge.
THROTTLE = os.path.join(os.path.dirname(MODEL), "throttle.gltf")
if os.path.exists(THROTTLE):
    lo, hi = _bounds(THROTTLE)
    mid = p(*[THROTTLE_PIVOT[i] + (lo[i] + hi[i]) / 2 for i in range(3)])
    must(batch([
        src("throttle_model", "Throttle lever", "model", {"file": asset(THROTTLE), "lighting": "scene"}),
        add("cockpit", "throttle", "throttle_model",
            geo(mid["x"], mid["y"], S * (hi[0] - lo[0]), S * (hi[1] - lo[1]), depth_px=mid["z"])),
    ], "throttle"), "throttle")

# ---- lights ----
def light(lid, name, settings, at, aim=None, size=60):
    q = p(*at)
    g = geo(q["x"], q["y"], size, size, depth_px=q["z"])
    if aim:
        g.update(aim)
    return [src(lid, name, "light", settings), add("cockpit", lid, lid, g)]


edits = []
# Soft fill so nothing goes black.
edits += light("l_ambient", "Ambient", {"type": "ambient", "color": "#8aa4c8", "intensity": 0.25},
               (0, 1.2, 0))
# The environment: a deep-space sky for reflections and ambient light.
# With SKY=1 (the default) it is also the backdrop behind everything, a deep-space sky
# that can warp (JStream ADR-0167); SKY=0 for a JStream without it.
SKY = os.environ.get("SKY", "1") == "1"
env = {"type": "environment", "intensity": 0.6,
       "sky_color": "#26385c", "horizon_color": "#6f86b0", "ground_color": "#0b0e14"}
if PAGES_URL:
    env.update({"image": {"type": "source", "source_id": "outside_src"}, "intensity": 1.4})
elif SKY:
    env.update({"backdrop": True, "sky_color": "#04060c", "horizon_color": "#070a14",
                "ground_color": "#020306", "stars": 0.55, "star_brightness": 1.6,
                "nebula": 0.45, "nebula_color": "#3a1460", "nebula_color_2": "#0d3a5c",
                "galaxy": 0.35, "sky_seed": 4127, "warp": 0.0, "warp_ramp_s": 1.5})
edits += light("l_env", "Space sky", env, (0, 1.2, 0))
# Starlight through the windshield, casting the frame's shadows into the cabin.
edits += light("l_sun", "Starlight", {"type": "directional", "color": "#ffe6c4", "intensity": 2.2,
                                      "shadows": True, "shadow_softness": 0.35},
               (0.6, 3.2, -4.0), aim={"tilt_deg": float(os.environ.get("SUN_TILT", "-35")), "turn_deg": float(os.environ.get("SUN_TURN", "192"))})
# Cool cabin lights overhead, and the monitors' glow on the dash.
edits += light("l_cabin", "Cabin", {"type": "point", "color": "#9fc4ff", "intensity": 0.8,
                                    "range_px": 3200}, (0.0, BOUNDS_MAX[1] - 0.1, -0.2))
edits += light("l_glow", "Screen glow", {"type": "point", "color": "#58d6ff", "intensity": 0.9,
                                         "range_px": 1100}, (0.0, 1.0, -1.15))
edits += light("l_rear", "Rear", {"type": "point", "color": "#ffb36b", "intensity": 0.6,
                                  "range_px": 2400}, (0.0, 1.6, BACK))
must(batch(edits, "lights"), "lights")

# ---- depth-aware scene filters ----
must(batch([
    flt({"type": "scene", "scene_id": "cockpit"}, "ao", "ambient_occlusion",
        {"radius_px": 60, "strength": 0.8}),
] + ([flt({"type": "scene", "scene_id": "cockpit"}, "bloom", "depth_bloom",
          {"threshold": 0.85, "strength": 0.9, "radius_px": 28, "depth_px": 300})]
     if os.environ.get("BLOOM", "0") == "1" else []), "filters"), "filters")

# ---- the shots, as keyframe variants, and the glide between them ----
for vid, shot in SHOTS.items():
    if vid == "cockpit":
        continue
    edits = [
        {"type": "scene.create_variant", "scene_id": vid, "variant_of": "cockpit",
         "name": f"Cockpit · {vid}"},
        {"type": "scene.set_camera", "scene_id": vid, "camera": shot},
    ]
    if vid == "warp":
        # Going to warp: the cabin lights go out, so only the screens, the LEDs and the
        # streaking sky light the cabin, and the planet is left behind. A light's
        # strength is its intensity times its item's opacity, so the glide dims them.
        edits += [{"type": "item.set_opacity", "scene_id": vid, "item_id": i, "opacity": o}
                  for i, o in [("l_ambient", 0.0), ("l_sun", 0.0), ("l_cabin", 0.0),
                               ("l_rear", 0.0), ("l_glow", 0.4)]]
        if PAGES_URL:
            edits.append({"type": "item.set_visible", "scene_id": vid, "item_id": "warp", "visible": True})
            edits.append({"type": "item.set_visible", "scene_id": vid, "item_id": "sky", "visible": False})
        else:
            edits.append({"type": "item.set_opacity", "scene_id": vid, "item_id": "space", "opacity": 0.0})
    must(batch(edits, vid), vid)

for pid, ms in [("glide", 3200), ("glide_long", 4200), ("glide_short", 2400)]:
    must(op({"type": "transition.create", "preset_id": pid, "name": f"Glide {ms} ms",
             "kind": "move", "duration_ms": min(int(ms * F), 60000), "easing": "ease_in_out"}),
         pid)

must(op({"type": "scene.switch", "scene_id": "cockpit"}), "switch")
print("built")
