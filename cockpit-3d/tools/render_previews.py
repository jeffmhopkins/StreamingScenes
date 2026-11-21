"""Renders preview stills of the cockpit from the .blend that build_cockpit.py saves.

    python render_previews.py <cockpit.blend> <out dir> [samples] [width]

These are Blender Cycles renders for the README, to show the model and its textures.
They are not JStream renders: JStream shades the exported glTF with its own lights.
"""
import math
import sys

import bpy
from mathutils import Vector

BLEND, OUT = sys.argv[1], sys.argv[2]
SAMPLES = int(sys.argv[3]) if len(sys.argv) > 3 else 64
WIDTH = int(sys.argv[4]) if len(sys.argv) > 4 else 1280

# name: (camera position, look-at point, focal length mm)
VIEWS = {
    "overview": ((0.0, -1.55, 1.55), (0.0, 1.2, 0.95), 16),
    "pilot": ((0.0, -0.45, 1.22), (0.0, 1.5, 0.95), 20),
    "dash-closeup": ((0.35, 0.72, 0.95), (0.55, 1.12, 0.64), 50),
    "button-macro": ((0.55, 0.98, 0.72), (0.56, 1.13, 0.645), 85),
    "seat": ((0.95, 0.75, 1.45), (0.0, -0.5, 0.75), 22),
    "left-console": ((-0.35, -0.2, 1.25), (-0.95, 0.3, 0.72), 28),
}


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = SAMPLES
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except TypeError:
        pass
    sc.render.resolution_x = WIDTH
    sc.render.resolution_y = WIDTH * 9 // 16
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("space")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.01, 0.015, 0.03, 1)
    bg.inputs["Strength"].default_value = 1.0
    sc.world = world
    # A cool key from the windshield, a warm fill from the back.
    for name, loc, energy, colour, size in [
        ("key", (0.0, 2.8, 2.6), 900, (0.75, 0.85, 1.0), 2.5),
        ("fill", (0.0, -1.2, 1.9), 120, (1.0, 0.85, 0.7), 1.2),
    ]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy = energy
        light.color = colour
        light.size = size
        ob = bpy.data.objects.new(name, light)
        ob.location = loc
        sc.collection.objects.link(ob)
        look_at(ob, (0, 0.6, 0.8))
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    only = sys.argv[5].split(",") if len(sys.argv) > 5 else list(VIEWS)
    for name in only:
        pos, target, lens = VIEWS[name]
        cam.location = pos
        look_at(cam, target)
        cam_data.lens = lens
        cam_data.clip_start = 0.01
        sc.render.filepath = f"{OUT}/{name}.jpg"
        bpy.ops.render.render(write_still=True)
        print("rendered", name, flush=True)


main()
