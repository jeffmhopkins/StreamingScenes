"""Builds the starship cockpit as a JStream scene over MCP.

Layers follow starship-cockpit/README.md. The reflections are native: scene sources of
the outside layers and of the lit interior, flipped and squashed, blurred, masked with
the gloss masks and blended additive. Effects are keyframe variants of one scene.

Pages are served over http from PAGES_URL (they read their images with getImageData,
which a file:// page can't). PAGES_DIR is where the masks and stills are on disk.
"""
import os, sys, json
from mcp import *

PAGES_URL = os.environ.get("PAGES_URL", "http://cockpit.test:8767")
PAGES_DIR = os.path.abspath(os.environ.get(
    "PAGES_DIR", os.path.join(os.path.dirname(__file__), "..", "pages")))
FPS = int(os.environ.get("PAGE_FPS", "30"))
# Pages carry translucent light (the warp and weapons spill, the red alert, the scan band).
# They blend in sRGB like a browser with JStream's normal_srgb; with plain `normal`, which
# blends in linear light, set SPILL to about 0.4 so the spill doesn't wash out the cockpit.
VEIL = os.environ.get("VEIL", "normal_srgb")
SPILL = os.environ.get("SPILL", "1")
# Reflections add in sRGB, like refl.js's canvas `lighter`, at refl.js's gains.
GLOSS = os.environ.get("GLOSS", "additive_srgb")


def page(sid, name, w=1920, h=1080, restart=False, fps=None, query=""):
    # The pages stay still (sway=0): drive.py moves every layer with one sway, so the plate,
    # its monitors and its reflections can't slip against each other.
    q = "?sway=0" + (f"&spill={SPILL}" if SPILL != "1" else "") + query
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": "browser"},
            "settings": {"url": f"{PAGES_URL}/{name}.html{q}", "width": w, "height": h,
                         "fps": fps or FPS, "restart_on_show": restart}}


def image(sid, file):
    return {"type": "source.create", "source_id": sid, "name": sid,
            "kind": {"type": "builtin", "kind": "image"},
            "settings": {"file": asset(f"{PAGES_DIR}/{file}")}}


def scene_src(sid, scene_id):
    return {"type": "source.create", "source_id": sid, "name": sid,
            "kind": {"type": "scene", "scene_id": scene_id}}


def add(scene, item, source, g=None, **kw):
    e = {"type": "item.add", "scene_id": scene, "item_id": item, "source_id": source,
         "geometry": g or geo(0, 0, W, H)}
    e.update(kw)
    return e


def flt(owner, fid, kind, settings):
    return {"type": "filter.add", "owner": owner, "chain": "video", "filter_id": fid,
            "kind": kind, "settings": settings}


def mirror(top, line, squash):
    """Geometry of a full-frame item flipped so that y=line lands on y=top and the frame
    above the line hangs below it, squashed by `squash`: y' = top + (line - y) * squash."""
    return geo(0, top - (H - line) * squash, W, H * squash, flip_v=True, fit_mode="stretch")


MON = [(482, 523, 345, 184), (835, 523, 333, 183), (1174, 523, 342, 184)]
OUTSIDE = ["sky_deep", "sky_nebula", "sky_planet", "win_deep", "wout_nebula",
           "win_nebula", "wout_planet", "attack"]
SCREENS = {"m1radar": ("screen-radar", 0), "m1nav": ("screen-nav", 0),
           "m3spec": ("screen-spectrum", 2), "m3shield": ("screen-shields", 2)}
OVERLAYS = ["hit", "tx", "bitwig"]

init()
e = [{"type": "canvas.set_size", "width": W, "height": H}]

# --- sources ---
e += [{"type": "source.create", "source_id": "black", "name": "Black",
       "kind": {"type": "builtin", "kind": "color"},
       "settings": {"color": "#000000ff", "width": W, "height": H}}]
for i in range(3):
    e.append(image(f"cam{i+1}", f"cam{i+1}.png"))
    e.append(page(f"hud{i+1}", f"screen-camhud-{i+1}", 690, 368, restart=True))
for sid, (name, _) in SCREENS.items():
    e.append(page(sid, name, 690, 368, restart=True))
e.append(page("cockpit", "cockpit"))
for loc in ["deep", "nebula", "planet"]:
    e.append(page(f"sky_{loc}", f"sky-{loc}"))
e += [page("win_deep", "warp-in-deep", restart=True),
      page("wout_nebula", "warp-out-nebula", restart=True),
      page("win_nebula", "warp-in-nebula", restart=True),
      page("wout_planet", "warp-out-planet", restart=True),
      page("attack", "attack", restart=True),
      page("hit", "hit", restart=True),
      page("tx", "transmission", restart=True),
      page("bitwig", "bitwig", restart=True),
      image("caller", "caller.png"), image("daw", "daw_holo.png")]

# --- groups: the outside, the monitors, the holograms, the overlays ---
e += [{"type": "scene.create", "scene_id": "g_outside", "name": "Outside", "role": "group"},
      {"type": "scene.create", "scene_id": "g_mons", "name": "Monitors", "role": "group"},
      {"type": "scene.create", "scene_id": "g_holo", "name": "Holograms", "role": "group"},
      {"type": "scene.create", "scene_id": "g_fx", "name": "Overlays", "role": "group"}]
for sid in OUTSIDE:
    e.append(add("g_outside", sid, sid, blend=VEIL))
for i, (x, y, w, h) in enumerate(MON):
    e.append(add("g_mons", f"cam{i+1}", f"cam{i+1}", geo(x, y, w, h, fit_mode="fill")))
    e.append(add("g_mons", f"hud{i+1}", f"hud{i+1}", geo(x, y, w, h, fit_mode="fill"),
                 blend=VEIL))
for sid, (_, m) in SCREENS.items():
    x, y, w, h = MON[m]
    e.append(add("g_mons", sid, sid, geo(x, y, w, h, fit_mode="fill")))
e += [add("g_holo", "caller", "caller", geo(700, 130, 520, 292, fit_mode="fill"),
          blend="screen", opacity=0.75),
      add("g_holo", "daw", "daw", geo(600, 84, 720, 405, fit_mode="fill"),
          blend="screen", opacity=0.85)]
for sid in OVERLAYS:
    e.append(add("g_fx", sid, sid, blend=VEIL))
e += [scene_src("s_outside", "g_outside"), scene_src("s_mons", "g_mons"),
      scene_src("s_holo", "g_holo"), scene_src("s_fx", "g_fx")]

# --- reflections ---
# console: three surfaces, each mirroring the glass from its own top edge (refl.js), so
# the window's lower band lands on the ledge, the side windows on the sills and the window
# base on the seat bolsters. (surface top, mirror line, squash, blur)
# refl.js blurs at half resolution, so its blurs are about these at full size; the last
# number is its gain.
CONSOLE = {"ledge": (698, 492, 0.45, 2.5, 1.8), "sill": (640, 600, 0.5, 4, 1.4),
           "seat": (958, 492, 0.4, 3.5, 1.7)}
for n, (top, line, k, _, _) in CONSOLE.items():
    e += [{"type": "scene.create", "scene_id": f"g_refl_{n}", "name": f"Reflection: {n}",
           "role": "group"},
          add(f"g_refl_{n}", f"r{n}_outside", "s_outside", mirror(top, line, k)),
          scene_src(f"s_refl_{n}", f"g_refl_{n}")]
# glass: the monitors, holograms and overlays mirrored about the window's lower edge
# (y 492), squashed to 0.8, faint.
e += [{"type": "scene.create", "scene_id": "g_refl_glass", "name": "Reflection: glass",
       "role": "group"},
      add("g_refl_glass", "rg_mons", "s_mons", mirror(492, 492, 0.8)),
      add("g_refl_glass", "rg_holo", "s_holo", mirror(492, 492, 0.8)),
      add("g_refl_glass", "rg_fx", "s_fx", mirror(492, 492, 0.8)),
      scene_src("s_refl_glass", "g_refl_glass")]

# --- the cockpit scene, bottom to top ---
e += [{"type": "scene.create", "scene_id": "cockpit", "name": "Cockpit"},
      add("cockpit", "black", "black"),
      add("cockpit", "mons", "s_mons"),
      add("cockpit", "cockpit_plate", "cockpit"),
      add("cockpit", "outside", "s_outside", blend=VEIL),
      *[add("cockpit", f"refl_{n}", f"s_refl_{n}", blend=GLOSS, opacity=g)
        for n, (_, _, _, _, g) in CONSOLE.items()],
      add("cockpit", "refl_edge", "s_outside", blend=GLOSS, opacity=3.2),
      add("cockpit", "refl_glass", "s_refl_glass", blend=GLOSS, opacity=0.2),
      add("cockpit", "holo", "s_holo"),
      add("cockpit", "fx", "s_fx", blend=VEIL),
      {"type": "source.create", "source_id": "key", "name": "Key label",
       "kind": {"type": "builtin", "kind": "text"},
       "settings": {"text": "F1  Cruise: deep space", "face": "bold", "size": 24,
                    "color": "#ffffffff", "background": "#000000c0", "padding": 12}},
      add("cockpit", "key", "key", geo(960 - 450, 1080 - 36 - 50, 900, 50), opacity=0.0)]

t, ok_ = batch(e, "build")
print("build", ok_, t[:200])
if not ok_:
    sys.exit(1)

# Filters: mask on the reflection scenes' sources; blur on their placements.
m = lambda n: {"image": asset(f"{PAGES_DIR}/{n}.png"), "mode": "luma"}
f = [x for n, (_, _, _, b, _) in CONSOLE.items() for x in (
         flt({"type": "item", "item_id": f"r{n}_outside"}, "blur", "blur", {"radius": b}),
         flt({"type": "source", "source_id": f"s_refl_{n}"}, "mask", "image_mask", m(f"m-{n}")))]
f += [
     flt({"type": "item", "item_id": "refl_edge"}, "blur", "blur", {"radius": 11}),
     flt({"type": "item", "item_id": "refl_edge"}, "mask", "image_mask", m("m-edge")),
     flt({"type": "source", "source_id": "s_refl_glass"}, "blur", "blur", {"radius": 3.5}),
     flt({"type": "source", "source_id": "s_refl_glass"}, "mask", "image_mask", m("m-glass")),
     flt({"type": "source", "source_id": "caller"}, "holo", "color_correction",
         {"saturation": -1, "multiply": "#78dcff"}),
     flt({"type": "source", "source_id": "daw"}, "holo", "color_correction",
         {"saturation": -1, "multiply": "#78dcff"})]
t, ok_ = batch(f, "filters")
print("filters", ok_, t[:200])

# Holograms fade in after the transmission or Bitwig frame has started.
for item, delay, dur in ([("caller", 1700, 400), ("daw", 1100, 500)] if os.environ.get("SLOW", "1") == "1" else []):
    op({"type": "item.set_transition", "item_id": item,
        "transition": {"delay_ms": delay, "appear": "fade", "disappear": "fade",
                       "easing": "ease_out"}})

# --- variants: one per state on the timeline (tools/rec.js) ---
SWITCHABLE = ["sky_deep", "sky_nebula", "sky_planet", "win_deep", "wout_nebula",
              "win_nebula", "wout_planet", "attack", "m1radar", "m1nav", "m3spec",
              "m3shield", "hit", "tx", "bitwig", "caller", "daw"]
VARIANTS = [
    ("cruise_deep", "Cruise: deep space", ["sky_deep"]),
    ("scan_deep", "Monitors: radar and audio", ["sky_deep", "m1radar", "m3spec"]),
    ("warp_deep", "Warp to the Kestrel Nebula", ["sky_deep", "m1radar", "m3spec", "win_deep"]),
    # Each arrival first shows the warp-out over the warp-in, which is still on its tunnel,
    # and drops the warp-in once the warp-out has loaded (a shown page reloads, and is
    # transparent until it paints).
    ("hold_nebula", "Arrive: Kestrel Nebula (warp-out loading)",
     ["sky_nebula", "m1radar", "m3spec", "win_deep", "wout_nebula"]),
    ("arrive_nebula", "Arrive: Kestrel Nebula", ["sky_nebula", "m1radar", "m3spec", "wout_nebula"]),
    ("nav_nebula", "Monitors: navigation", ["sky_nebula", "m1nav", "m3spec", "wout_nebula"]),
    ("weapons_nebula", "Weapons: destroy target", ["sky_nebula", "m1radar", "m3spec", "wout_nebula", "attack"]),
    ("hit_nebula", "Taking fire", ["sky_nebula", "m1radar", "m3shield", "wout_nebula", "hit"]),
    ("warp_nebula", "Warp to Tyr VII", ["sky_nebula", "m1nav", "m3shield", "wout_nebula", "win_nebula"]),
    ("hold_planet", "Arrive: Tyr VII (warp-out loading)",
     ["sky_planet", "m1nav", "m3spec", "win_nebula", "wout_planet"]),
    ("arrive_planet", "Arrive: Tyr VII", ["sky_planet", "m1nav", "m3spec", "wout_planet"]),
    ("tx_planet", "Incoming transmission", ["sky_planet", "m1nav", "m3spec", "wout_planet", "tx", "caller"]),
    ("bitwig_planet", "Bitwig hologram", ["sky_planet", "m1nav", "m3spec", "wout_planet", "bitwig", "daw", "caller"]),
]
# The parent hides everything switchable; each variant shows its set.
t, ok_ = batch([{"type": "item.set_visible", "item_id": i, "visible": False} for i in SWITCHABLE],
               "hide")
print("hide", ok_)
for vid, name, shown in VARIANTS:
    ed = [{"type": "scene.create_variant", "scene_id": vid, "variant_of": "cockpit", "name": name}]
    ed += [{"type": "item.set_visible", "scene_id": vid, "item_id": i, "visible": True} for i in shown]
    t, ok_ = batch(ed, vid)
    print(vid, ok_)

# Holograms start transparent where shown; their fades come from item transitions at real
# speed, and from the capture driver in a slowed capture.
if os.environ.get("SLOW", "1") != "1":
    batch([{"type": "item.set_opacity", "scene_id": v, "item_id": i, "opacity": 0.0}
           for v, i in [("tx_planet", "caller"), ("bitwig_planet", "daw")]], "holo")

# A recording profile with bits enough for 1080p, and a keyframe every 10 s.
op({"type": "encoder.create", "profile_id": "hq", "name": "Recording, high quality",
    "profile": {"video": {"codec": "h264", "hardware": "avoid", "keyframe_interval_s": 10,
                          "rate_control": {"type": "vbr", "kbps": 20000, "max_kbps": 40000}},
                "audio": {"codec": "aac", "kbps": 128}}})
