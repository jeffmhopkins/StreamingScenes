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
    "overview": ((0.0, -0.98, 1.4), (0.0, 1.2, 1.0), 13),
    "pilot": ((0.0, -0.3, 1.22), (0.0, 1.4, 1.14), 14),
    "desk": ((0.0, 0.2, 1.15), (0.0, 0.98, 0.72), 20),
    "dash-closeup": ((0.25, 0.55, 1.0), (0.6, 1.1, 0.72), 40),
    "button-macro": ((0.55, 0.85, 0.85), (0.64, 1.1, 0.73), 85),
    "canopy": ((-0.3, -0.6, 1.2), (0.7, 0.9, 1.3), 14),
    "windshield": ((0.0, 0.0, 1.25), (0.0, 1.6, 1.36), 14),
    "left-console": ((-0.1, -0.2, 1.2), (-0.9, 0.3, 0.72), 24),
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
    nt = world.node_tree
    bg = nt.nodes["Background"]
    # Stars: a point at the centre of each Voronoi cell, over a faint blue.
    noise = nt.nodes.new("ShaderNodeTexVoronoi")
    noise.inputs["Scale"].default_value = 120.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (4.0, 4.0, 4.2, 1)
    ramp.color_ramp.elements[1].position = 0.09
    ramp.color_ramp.elements[1].color = (0.003, 0.005, 0.012, 1)
    nt.links.new(noise.outputs["Distance"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    sc.world = world
    # A cool key from the windshield, a warm fill from the back.
    for name, loc, energy, colour, size in [
        ("key", (0.0, 3.2, 2.4), 420, (0.7, 0.8, 1.0), 2.5),
        ("side", (3.0, 0.4, 1.6), 120, (0.7, 0.8, 1.0), 2.0),
        ("fill", (0.0, -0.9, 1.7), 30, (1.0, 0.75, 0.5), 1.2),
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
