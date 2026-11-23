"""Where a warp arrives: the pictures in arrivals/, shown in the cockpit's sky one at a time,
a new one each time the warp drops out (JStream ADR-0188).

The sky's `sky_pictures` names a group scene, `arrivals`, whose visible items are the
candidates. Each picture's width in the sky is `sky_picture_deg` (100 here) times its
item's width over the canvas width, so each item is sized from `SIZE` below, the
picture's width in degrees. The nebulae and the galaxy span most of the window; the planets are
small enough to look a good way off.

With SUNS=1, each planet arrives with its star: the planet's item shows a small scene of
two pictures, the planet at the bottom (pinned ahead) and its sun on top, pinned by the
item's turn_deg and tilt_deg from the planet so the planet's lit side faces it
(arrivals/sun_directions.json, written by arrivals/src/render_all.py). The sun is behind
the ship's shoulder for most of them, so turning the ship finds it, and it is the one
that lights the scene. That needs a JStream with ADR-0198's companions; an older one
leaves out an item that shows a scene, so SUNS is off by default until that lands.

Build from build_daw.py: `edits()` returns the scene, and `patch()` the sky's settings.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "arrivals")
SCENE = "arrivals"
# The engine sizes a picture by its item's width over the program canvas's width, which
# build_daw.py sets to 1920 x 1080. A project given another canvas width scales every
# arrival by 1920 over it: change these to match.
CANVAS_W, CANVAS_H = 1920, 1080
SKY_DEG = 100.0
# Each picture's width across the sky, in degrees (its item's width is this / SKY_DEG of
# the canvas). A planet's disc is about 0.8 of its picture, a ringed one's 0.4; the
# black hole's shadow is about a fifth of its picture.
SIZE = {
    "emission_nebula": 80,
    "spiral_galaxy": 75,
    "blue_nebula": 70,
    "ring_nebula": 50,
    "black_hole": 50,
    "ringed_giant": 36,
    "ice_giant": 30,
    "violet_giant": 24,
    "ocean_world": 20,
    "red_desert": 18,
    "moon_grey": 16,
    "lava_world": 15,
}
SUN_DEG = 8  # the sun picture's width; its disc is about a tenth of it
NAMES = {
    "emission_nebula": "Emission nebula", "spiral_galaxy": "Spiral galaxy",
    "blue_nebula": "Reflection nebula", "ring_nebula": "Ring nebula", "black_hole": "Black hole",
    "ringed_giant": "Ringed giant", "ice_giant": "Ice giant", "violet_giant": "Violet giant",
    "ocean_world": "Ocean world", "red_desert": "Desert world", "moon_grey": "Grey moon",
    "lava_world": "Lava world", "sun_yellow": "Yellow sun", "sun_orange": "Orange sun",
}


def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _image(sid, name, path):
    # mcp.asset() builds the same; importing mcp needs a token, and this stays importable without one.
    return {"type": "source.create", "source_id": sid, "name": name,
            "kind": {"type": "builtin", "kind": "image"},
            "settings": {"file": {"type": "asset", "root": "absolute", "path": path}}}


def _item(scene, item, source, deg, aspect, **pose):
    w = CANVAS_W * deg / SKY_DEG
    g = {"center": {"x": CANVAS_W / 2, "y": CANVAS_H / 2}, "size": {"width": w, "height": w * aspect}}
    g.update(pose)
    return {"type": "item.add", "scene_id": scene, "item_id": item, "source_id": source, "geometry": g}


def _group(sid, name):
    return [{"type": "scene.create", "scene_id": sid, "name": name, "role": "group"},
            {"type": "source.create", "source_id": sid, "name": name,
             "kind": {"type": "scene", "scene_id": sid}, "settings": {}}]


def edits(suns=False):
    with open(os.path.join(ART, "sun_directions.json"), encoding="utf-8") as f:
        sun_of = json.load(f)
    out = _group(SCENE, "Arrivals")
    made = set()
    for name, deg in SIZE.items():
        path = os.path.join(ART, f"{name}.png")
        w, h = _png_size(path)
        sid = f"arr_{name}"
        out.append(_image(sid, NAMES[name], path))
        if not (suns and name in sun_of):
            out.append(_item(SCENE, sid, sid, deg, h / w))
            continue
        s = sun_of[name]
        star = f"arr_{s['sun']}"
        if star not in made:
            spath = os.path.join(ART, f"{s['sun']}.png")
            out.append(_image(star, NAMES[s["sun"]], spath))
            made.add(star)
        sw, sh = _png_size(os.path.join(ART, f"{s['sun']}.png"))
        system = f"sys_{name}"
        out += _group(system, f"{NAMES[name]} and its sun")
        # Bottom: the planet, pinned ahead. Top: its sun, pinned from the planet.
        out.append(_item(system, f"{system}_planet", sid, deg, h / w))
        out.append(_item(system, f"{system}_sun", star, SUN_DEG, sh / sw,
                         turn_deg=s["yaw_deg"], tilt_deg=s["pitch_deg"]))
        out.append(_item(SCENE, system, system, deg, h / w))
    return out


def patch(light):
    return {"sky_pictures": {"type": "scene", "scene_id": SCENE}, "sky_picture_deg": SKY_DEG,
            "sky_picture_light": light}
