"""Builds the cockpit model in Blender and exports it as glTF 2.0.

Run with Blender's Python module (pip install bpy) or `blender -b -P`:

    python build_cockpit.py <textures dir> <out .gltf> [--blend out.blend]

Everything is built from code: boxes, extruded profiles and cylinders, bevelled, with
texture coordinates box-projected in world metres so each tiling texture set keeps the
same texel density everywhere (see TILE). Screens and decals keep their own coordinates.

Blender axes: x right, y forward (toward the windshield), z up. glTF export turns that
into x right, y up, z toward the viewer, so the pilot looks down glTF -z.

The export leaves images out; finish_gltf.py wires the texture sets into the file, so
the glTF holds exactly the images in ../model/textures and nothing re-encoded.
"""
import math
import random
import re
import sys

import bpy  # first: it makes bmesh and mathutils importable
import bmesh
from mathutils import Euler, Matrix, Vector

import os  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_panels  # noqa: E402  the console's live displays, shared with add_live_panels.py

# Texture tile sizes in metres per repeat, per tiling material.
TILE = {
    "paint": 0.5,
    "paint_dark": 0.5,
    "floor": 0.6,
    "leather": 0.3,
    "plastic": 0.4,
    "hexpanel": 0.5,
    "panel": 0.8,
}
SETS = {  # material -> texture set
    "paint": "paint",
    "paint_dark": "paint",
    "floor": "floor",
    "leather": "leather",
    "plastic": "plastic",
    "hexpanel": "hexpanel",
    "panel": "panel",
}
NORMAL_SCALE = {"plastic": 0.35, "paint": 0.6, "paint_dark": 0.6}
SCREENS = {
    # name: (width m, centre, euler degrees (x tilt, y, z yaw))
    # Three equal monitors wrapped around the pilot: one ahead, one angled in each side.
    "screen_center": (0.52, (0.0, 1.44, 0.97), (-10, 0, 0)),
    "screen_left": (0.52, (-0.56, 1.335, 0.97), (-10, 0, 22)),
    "screen_right": (0.52, (0.56, 1.335, 0.97), (-10, 0, -22)),
    "screen_side_left": (0.22, (-0.95, 0.5, 0.86), (-50, 0, 75)),
    "screen_side_right": (0.22, (0.95, 0.5, 0.86), (-50, 0, -75)),
    # Lying on the tray in front of the pilot, its far edge raised a little and butted
    # against the console. The instrument's playing surface: 8:3 (see DESK_ASPECT).
    "screen_desk": (0.72, (0.0, 0.92, 0.69), (-78, 0, 0)),
    # Set flush into the face of the overhead console, which is tilted at the pilot's eyes.
    "screen_overhead_left": (0.3, (-0.38, 0.62, 1.70), (31, 0, 0)),
    "screen_overhead_right": (0.3, (0.38, 0.62, 1.70), (31, 0, 0)),
}
# Every screen shares one material, `screens`, and one 1920 x 1080 image: a 3 x 3 grid of
# 640 x 360 cells, (column, row) from the top left. The desk instrument is 8:3 and takes
# the left 960 x 360 of the bottom row.
SCREEN_CELLS = {
    "screen_left": (0, 0), "screen_center": (1, 0), "screen_right": (2, 0),
    "screen_overhead_left": (0, 1), "screen_overhead_right": (1, 1), "screen_side_left": (2, 1),
    "screen_desk": (0, 2), "screen_side_right": (2, 2),
}
LEDS = {
    "led_green": (0.15, 1.0, 0.35),
    "led_amber": (1.0, 0.55, 0.05),
    "led_red": (1.0, 0.08, 0.05),
    "led_blue": (0.15, 0.55, 1.0),
    "light_strip": (1.0, 0.62, 0.2),
    # Dim orange accent grooves along the pillars, sills and console edges.
    "glow_amber": (1.0, 0.42, 0.08),
}
# The big structural surfaces take the panelled-metal set instead of plain paint.
PANELLED = re.compile(r"^(wall_[LR]\d\d|ceiling_\d\d|console_centre|console_wing_[LR]|console_[LR]|"
                      r"cheek_-?1|roof_front|overhead|ledge_[LR]|desk|bulkhead|monitor_bank)$")

ATLAS = 2048
DECALS = {  # same table as make_textures.py: x, y, w, h in atlas pixels
    "stripe": (0, 0, 2048, 128),
    "label_nav": (0, 256, 512, 128),
    "label_comms": (512, 256, 512, 128),
    "label_power": (1024, 256, 512, 128),
    "label_sensors": (1536, 256, 512, 128),
    "label_engines": (0, 384, 512, 128),
    "label_shields": (512, 384, 512, 128),
    "label_aux": (1024, 384, 512, 128),
    "label_lifesupport": (1536, 384, 512, 128),
    "warn_eject": (0, 512, 1024, 256),
    "warn_hatch": (1024, 512, 1024, 256),
    "serial": (0, 768, 1024, 128),
    "scale": (1024, 768, 1024, 128),
    "deck_number": (0, 1024, 512, 512),
    "arrow": (512, 1024, 512, 512),
    "keypad": (1024, 1024, 1024, 512),
    "grid_labels": (0, 1536, 2048, 512),
}

import os
TEX = os.path.abspath(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else sys.argv[1])
OUT = sys.argv[sys.argv.index("--") + 2] if "--" in sys.argv else sys.argv[2]
BLEND = sys.argv[sys.argv.index("--blend") + 1] if "--blend" in sys.argv else None

# ---------------------------------------------------------------------------- materials

MATS = {}


def image(path, colour=True):
    img = bpy.data.images.load(path, check_existing=True)
    if not colour:
        img.colorspace_settings.name = "Non-Color"
    return img


def make_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    out = nt.nodes["Material Output"]
    link = nt.links.new

    def tex(path, colour=True):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = image(path, colour)
        return n

    if name in SETS:
        s = f"{TEX}/{SETS[name]}"
        c = tex(f"{s}-color.jpg")
        if name == "paint_dark":
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            mix.inputs[7].default_value = (0.45, 0.45, 0.47, 1)
            link(c.outputs["Color"], mix.inputs[6])
            link(mix.outputs[2], bsdf.inputs["Base Color"])
        else:
            link(c.outputs["Color"], bsdf.inputs["Base Color"])
        orm = tex(f"{s}-orm.jpg", False)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        link(orm.outputs["Color"], sep.inputs["Color"])
        link(sep.outputs["Green"], bsdf.inputs["Roughness"])
        link(sep.outputs["Blue"], bsdf.inputs["Metallic"])
        nrm = tex(f"{s}-normal.jpg", False)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = NORMAL_SCALE.get(name, 1.0)
        link(nrm.outputs["Color"], nm.inputs["Color"])
        link(nm.outputs["Normal"], bsdf.inputs["Normal"])
    elif name == "screens":
        c = tex(f"{TEX}/{name}.jpg")
        em = nt.nodes.new("ShaderNodeEmission")
        link(c.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = 1.0
        link(em.outputs["Emission"], out.inputs["Surface"])
    elif name in LEDS:
        col = LEDS[name]
        bsdf.inputs["Base Color"].default_value = (*[c * 0.3 for c in col], 1)
        bsdf.inputs["Emission Color"].default_value = (*col, 1)
        bsdf.inputs["Emission Strength"].default_value = {"light_strip": 2.5, "glow_amber": 1.6}.get(name, 5.0)
        bsdf.inputs["Roughness"].default_value = 0.35
    elif name == "readout":
        c = tex(f"{TEX}/readouts.png")
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1)
        link(c.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
        bsdf.inputs["Roughness"].default_value = 0.2
    elif name == "glass":
        # Nearly black and nearly clear: a pale tint lights up like a wall under the
        # scene's lights, so the glass only adds a faint darkening and its reflections.
        bsdf.inputs["Base Color"].default_value = (0.02, 0.03, 0.04, 1)
        bsdf.inputs["Roughness"].default_value = 0.02
        bsdf.inputs["Alpha"].default_value = 0.05
        m.surface_render_method = "BLENDED"
    elif name == "decals":
        c = tex(f"{TEX}/decals.png")
        link(c.outputs["Color"], bsdf.inputs["Base Color"])
        link(c.outputs["Alpha"], bsdf.inputs["Alpha"])
        bsdf.inputs["Roughness"].default_value = 0.5
        m.surface_render_method = "DITHERED"
    return m


def mat(name):
    if name not in MATS:
        MATS[name] = make_material(name)
    return MATS[name]


# ---------------------------------------------------------------------------- geometry

ALL = []
GROUP = ["cabin"]  # the node an object joins into at export (see finish)
PIVOT = [0.0, 0.0, 0.0]  # the throttle lever's hinge, set in build_side_consoles


def new_object(name, bm, material):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    if material in ("paint", "paint_dark") and PANELLED.match(name):
        material = "panel"
    ob.data.materials.append(mat(material))
    ob["group"] = GROUP[0]
    ALL.append(ob)
    return ob


def place(ob, loc=(0, 0, 0), rot=(0, 0, 0)):
    ob.matrix_world = Matrix.Translation(Vector(loc)) @ Euler(
        [math.radians(a) for a in rot], "XYZ"
    ).to_matrix().to_4x4()
    return ob


def bevel(ob, width, segments=2):
    if width <= 0:
        return ob
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(40)
    mod.harden_normals = False
    return ob


def box(name, size, loc, rot=(0, 0, 0), material="paint", bev=0.006, segs=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = new_object(name, bm, material)
    place(ob, loc, rot)
    return bevel(ob, bev, segs)


def cyl(name, r, depth, loc, rot=(0, 0, 0), material="paint_dark", segs=24, bev=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth
    )
    ob = new_object(name, bm, material)
    place(ob, loc, rot)
    return bevel(ob, bev, 2)


def bolt(name, loc, normal, r=0.006, material="paint_dark"):
    """A hex bolt head standing on a surface: loc on the surface, normal out of it."""
    n = Vector(normal).normalized()
    ob = cyl(name, r, 0.006, (0, 0, 0), material=material, segs=6, bev=0.0012)
    ob.matrix_world = Matrix.Translation(Vector(loc) + n * 0.002) @ (
        Vector((0, 0, 1)).rotation_difference(n).to_matrix().to_4x4())
    return ob


def bolts(name, corners, normal, inset=0.03, **kw):
    """Four bolts inset from the corners of a quad."""
    c = [Vector(p) for p in corners]
    centre = sum(c, Vector()) / len(c)
    for k, p in enumerate(c):
        d = centre - p
        bolt(f"{name}_bolt{k}", p + d.normalized() * inset * 1.414, normal, **kw)


def prism(name, profile, axis, a0, a1, material="paint", bev=0.008, segs=2):
    """Extrudes a closed 2D profile along an axis. axis 'x': profile is (y, z);
    'y': profile is (x, z)."""
    bm = bmesh.new()
    if axis == "x":
        verts = [bm.verts.new((a0, p[0], p[1])) for p in profile]
        d = Vector((a1 - a0, 0, 0))
    else:
        verts = [bm.verts.new((p[0], a0, p[1])) for p in profile]
        d = Vector((0, a1 - a0, 0))
    face = bm.faces.new(verts)
    ext = bmesh.ops.extrude_face_region(bm, geom=[face])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=d, verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_object(name, bm, material)
    return bevel(ob, bev, segs)


def slab(name, corners, thickness, material="paint", bev=0.004, inward=None):
    """A flat panel from 4+ coplanar corners, thickened along its normal (toward
    `inward`, a point the thickness grows toward, if given)."""
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in corners]
    f = bm.faces.new(vs)
    bm.normal_update()
    n = f.normal.copy()
    if inward is not None and n.dot(Vector(inward) - f.calc_center_median()) < 0:
        n = -n
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    moved = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=n * thickness, verts=moved)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_object(name, bm, material)
    return bevel(ob, bev, 2)


def quad(name, w, h, loc, rot, material, uv=(0, 0, 1, 1)):
    """A one-sided rectangle in the local x/z plane facing local -y, with its own texture
    coordinates: u along x, v along z (v up, as Blender has it)."""
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    hw, hh = w / 2, h / 2
    pts = [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)]
    u0, v0, u1, v1 = uv
    uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    for loop, t in zip(f.loops, uvs):
        loop[uvl].uv = t
    # This winding is counter-clockwise seen from -y, so the face looks down -y.
    ob = new_object(name, bm, material)
    ob["keep_uv"] = True
    return place(ob, loc, rot)


def decal(key, width, loc, rot, name=None, repeat=1.0):
    x, y, w, h = DECALS[key]
    height = width * h / w / repeat
    u0, u1 = x / ATLAS, (x + w * repeat) / ATLAS
    v1, v0 = 1 - y / ATLAS, 1 - (y + h) / ATLAS
    return quad(name or f"decal_{key}", width, height, loc, rot, "decals", (u0, v0, u1, v1))


# ---------------------------------------------------------------------------- the cabin

# A compact pod. Wall cross-section (x, z) for the right side behind the side windows;
# the left mirrors it. Forward of Y_FRONT the hull tapers in plan to the windshield.
WALL = [(1.05, 0.0), (1.05, 0.95), (0.82, 1.85)]
CEIL_Z = 1.85
SILL_Z = 0.95             # the bottom of every window
Y_BACK, Y_FRONT, Y_NOSE = -1.10, -0.10, 1.70  # rear bulkhead, B-pillar, windshield base
NOSE_HALF_W = 0.88        # half the windshield's width at its base
TOP_Y, TOP_HALF_W = 0.85, 0.73  # where the windshield meets the roof, and half its width (0.73 keeps each side pane flat)


def wall_x(z):
    for (x0, z0), (x1, z1) in zip(WALL, WALL[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return x0 + (x1 - x0) * t
    return WALL[-1][0]


def hull_x(y):
    """Half the hull's width at the sill, at station y."""
    if y <= Y_FRONT:
        return WALL[1][0]
    t = (y - Y_FRONT) / (Y_NOSE - Y_FRONT)
    return WALL[1][0] + (NOSE_HALF_W - WALL[1][0]) * t


def build_shell():
    GROUP[0] = "cabin"
    # A dark backing shell behind the wall panels, so the seams between them read dark.
    for side in (-1, 1):
        prof = [(side * (x + 0.04), z) for x, z in WALL]
        for i, ((x0, z0), (x1, z1)) in enumerate(zip(prof, prof[1:])):
            slab(f"shell_{'L' if side < 0 else 'R'}{i}",
                 [(x0, Y_BACK, z0), (x0, Y_FRONT, z0), (x1, Y_FRONT, z1), (x1, Y_BACK, z1)],
                 0.02, "paint_dark", 0, inward=(0, 0, 1.0))
    slab("shell_ceiling", [(-0.86, Y_BACK, CEIL_Z + 0.04), (0.86, Y_BACK, CEIL_Z + 0.04),
                           (0.86, Y_FRONT, CEIL_Z + 0.04), (-0.86, Y_FRONT, CEIL_Z + 0.04)],
         0.02, "paint_dark", 0, inward=(0, 0, 0))

    # Wall panels behind the side windows: between the ribs, one per profile segment.
    ribs = [Y_BACK, -0.6, Y_FRONT]
    gap = 0.008
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        for j, (ya, yb) in enumerate(zip(ribs, ribs[1:])):
            for i, ((x0, z0), (x1, z1)) in enumerate(zip(WALL, WALL[1:])):
                d0 = Vector((x1 - x0, z1 - z0)).normalized() * gap
                material = "hexpanel" if (i == 1 and j == 0) else "paint"
                slab(f"wall_{s}{j}{i}",
                     [(side * (x0 + d0.x), ya + gap, z0 + d0.y),
                      (side * (x0 + d0.x), yb - gap, z0 + d0.y),
                      (side * (x1 - d0.x), yb - gap, z1 - d0.y),
                      (side * (x1 - d0.x), ya + gap, z1 - d0.y)],
                     0.025, material, 0.005, inward=(side * 3.0, (ya + yb) / 2, (z0 + z1) / 2))
                n = Vector((-(z1 - z0), 0, x1 - x0)).normalized()
                n = Vector((side * n.x, 0, n.z))
                if n.dot(Vector((-side, 0, 0.3))) < 0:
                    n = -n
                if material == "paint":
                    bolts(f"wall_{s}{j}{i}",
                          [(side * x0, ya, z0), (side * x0, yb, z0), (side * x1, yb, z1),
                           (side * x1, ya, z1)], n, inset=0.035)
        for i, ((x0, z0), (x1, z1)) in enumerate(zip(WALL, WALL[1:])):
            y = ribs[1]
            slab(f"rib_{s}{i}",
                 [(side * (x0 - 0.02), y - 0.03, z0), (side * (x0 - 0.02), y + 0.03, z0),
                  (side * (x1 - 0.02), y + 0.03, z1), (side * (x1 - 0.02), y - 0.03, z1)],
                 0.05, "paint_dark", 0.008, inward=(0, y, 1.0))
    for j, y in enumerate(ribs[1:]):
        box(f"rib_ceiling{j}", (1.6, 0.07, 0.05), (0, y, CEIL_Z - 0.025), material="paint_dark")

    # Ceiling behind the canopy: panels with a hex vent in the middle and light strips.
    for j, (ya, yb) in enumerate(zip(ribs, ribs[1:])):
        for k, (xa, xb) in enumerate([(-0.8, -0.27), (-0.27, 0.27), (0.27, 0.8)]):
            m = "hexpanel" if k == 1 else "paint"
            box(f"ceiling_{j}{k}", (xb - xa - 0.012, yb - ya - 0.012, 0.025),
                ((xa + xb) / 2, (ya + yb) / 2, CEIL_Z - 0.0125), material=m, bev=0.004)
        for side in (-1, 1):
            box(f"light_strip_{j}{side}", (0.04, yb - ya - 0.14, 0.02),
                (side * 0.66, (ya + yb) / 2, CEIL_Z - 0.035), material="light_strip", bev=0.004)

    # Floor: diamond plate in two halves.
    for k, (ya, yb) in enumerate([(Y_BACK, 0.2), (0.2, Y_NOSE)]):
        box(f"floor_{k}", (2.1, yb - ya - 0.01, 0.03), (0, (ya + yb) / 2, -0.015),
            material="floor", bev=0.003)
    for side in (-1, 1):
        box(f"floor_kick_{side}", (0.06, Y_FRONT - Y_BACK, 0.10),
            (side * 1.0, (Y_FRONT + Y_BACK) / 2, 0.05), material="paint_dark")
    decal("stripe", 1.2, (0, -0.9, 0.002), (-90, 0, 0), name="decal_stripe_floor", repeat=4)
    decal("deck_number", 0.3, (0.4, -0.62, 0.002), (-90, 0, 0))
    decal("arrow", 0.24, (-0.4, -0.62, 0.002), (-90, 0, 0))

    # Pipes along both walls behind the consoles, with clamps.
    for side in (-1, 1):
        for z, r in [(1.12, 0.028), (1.2, 0.018)]:
            cyl(f"pipe_{side}_{z}", r, Y_FRONT - Y_BACK - 0.1, (side * (wall_x(z) - 0.07), (Y_BACK + Y_FRONT) / 2, z),
                (90, 0, 0), "paint_dark", 20)
        for y in (-0.95, -0.35):
            box(f"clamp_{side}_{y}", (0.06, 0.04, 0.16), (side * (wall_x(1.16) - 0.06), y, 1.16),
                material="plastic", bev=0.006)


def build_rear():
    GROUP[0] = "rear_bulkhead"
    # Rear bulkhead following the wall profile, with a hatch.
    prof = [(-x, z) for x, z in reversed(WALL)] + list(WALL)
    prof = [(x * 0.999, z) for x, z in prof]
    bm = bmesh.new()
    vs = [bm.verts.new((x, Y_BACK, z)) for x, z in prof]
    bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    bmesh.ops.translate(bm, vec=(0, -0.05, 0),
                        verts=[e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = new_object("bulkhead", bm, "paint")
    cutter = box("_cut", (0.8, 0.4, 1.7), (0, Y_BACK, 0.9), material="paint", bev=0)
    b = ob.modifiers.new("hatch", "BOOLEAN")
    b.object = cutter
    b.operation = "DIFFERENCE"
    b.solver = "EXACT"
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.modifier_apply(modifier="hatch")
    ALL.remove(cutter)
    bpy.data.objects.remove(cutter)
    bevel(ob, 0.006)
    # Hatch frame and door.
    box("hatch_frame_top", (0.96, 0.1, 0.08), (0, Y_BACK + 0.02, 1.79), material="paint_dark")
    for side in (-1, 1):
        box(f"hatch_frame_{side}", (0.08, 0.1, 1.76), (side * 0.44, Y_BACK + 0.02, 0.88),
            material="paint_dark")
    box("hatch_door", (0.8, 0.04, 1.7), (0, Y_BACK - 0.04, 0.9), material="hexpanel", bev=0.01)
    box("hatch_wheel_hub", (0.12, 0.06, 0.12), (0, Y_BACK + 0.0, 1.0), material="plastic", bev=0.02)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.17, minor_radius=0.018,
                                     location=(0, Y_BACK + 0.02, 1.0), rotation=(math.pi / 2, 0, 0))
    t = bpy.context.active_object
    t.name = "hatch_wheel"
    t.data.materials.append(mat("paint_dark"))
    t["group"] = GROUP[0]
    ALL.append(t)
    for a in range(3):
        box(f"hatch_spoke{a}", (0.34, 0.02, 0.025), (0, Y_BACK + 0.02, 1.0), (0, a * 60, 0),
            material="paint_dark", bev=0.003)
    decal("warn_hatch", 0.6, (0, Y_BACK + 0.012, 1.45), (0, 0, 180), name="decal_warn_hatch")
    for side in (-1, 1):
        decal("stripe", 1.6, (side * 0.51, Y_BACK + 0.012, 0.9), (0, 90, 180),
              name=f"decal_stripe_hatch_{side}", repeat=6)
        box(f"rear_light_{side}", (0.06, 0.03, 0.3), (side * 0.62, Y_BACK + 0.015, 1.5),
            material="led_red", bev=0.005)


def strut(name, a, b, w=0.05, t=0.05, material="paint_dark", bev=0.008):
    """A frame member from point a to point b, w wide and t deep."""
    a, b = Vector(a), Vector(b)
    d = b - a
    ob = box(name, (w, d.length + w * 0.5, t), (0, 0, 0), material=material, bev=bev)
    ob.matrix_world = Matrix.Translation((a + b) / 2) @ (
        Vector((0, 1, 0)).rotation_difference(d.normalized()).to_matrix().to_4x4())
    return ob


def pane(name, pts, material="glass"):
    """A single face through the given points (it need not be flat)."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(p) for p in pts])
    return new_object(name, bm, material)


def build_nose():
    """The canopy: a wide raked windshield and one big angled window each side, in thick
    pillars, over an opaque hull below the sill."""
    GROUP[0] = "windshield"
    fb = [Vector((s * NOSE_HALF_W, Y_NOSE, SILL_Z)) for s in (-1, 1)]
    ft = [Vector((s * TOP_HALF_W, TOP_Y, CEIL_Z)) for s in (-1, 1)]
    sb = [Vector((s * WALL[1][0], Y_FRONT, SILL_Z)) for s in (-1, 1)]
    st = [Vector((s * WALL[2][0], Y_FRONT, CEIL_Z)) for s in (-1, 1)]
    centre = Vector((0, 0.5, 1.35))
    # Below the sill: cheeks tapering to the nose, and the nose wall.
    for k, side in enumerate((-1, 1)):
        slab(f"cheek_{side}", [(sb[k].x, Y_FRONT, 0), (fb[k].x, Y_NOSE, 0), fb[k], sb[k]],
             0.03, "paint", 0.004, inward=(side * 3.0, 1.5, 0.5))
    slab("nose_lower", [(-NOSE_HALF_W, Y_NOSE, 0), (NOSE_HALF_W, Y_NOSE, 0), fb[1], fb[0]],
         0.04, "paint_dark", 0.004, inward=(0, 3.0, 0.5))
    # Glass.
    pane("glass_front", [fb[0], fb[1], ft[1], ft[0]])
    strut("canopy_sill_front", fb[0], fb[1], 0.09, 0.08)
    strut("canopy_top_front", ft[0], ft[1], 0.12, 0.08)
    box("canopy_sill_hump", (0.34, 0.1, 0.07), (0, Y_NOSE - 0.03, SILL_Z + 0.05),
        material="paint_dark", bev=0.02, segs=3)
    box("canopy_sill_hump_led", (0.05, 0.006, 0.008), (0, Y_NOSE - 0.081, SILL_Z + 0.05),
        material="led_amber", bev=0)

    def inset(a, b, d):
        """The segment a-b moved d toward the cabin's centre and shortened."""
        mid = (a + b) / 2
        off = (centre - mid).normalized() * d
        return a.lerp(b, 0.12) + off, a.lerp(b, 0.88) + off

    for k, side in enumerate((-1, 1)):
        s = "L" if side < 0 else "R"
        pane(f"glass_side_{s}", [fb[k], sb[k], st[k], ft[k]])
        strut(f"canopy_pillar_a_{s}", fb[k], ft[k], 0.13, 0.10, bev=0.02)
        strut(f"canopy_pillar_b_{s}", sb[k], st[k], 0.14, 0.11, bev=0.02)
        strut(f"canopy_sill_{s}", fb[k], sb[k], 0.10, 0.08)
        strut(f"canopy_top_{s}", ft[k], st[k], 0.10, 0.08)
        gp, gq = inset(fb[k], sb[k], 0.052)
        strut(f"canopy_glow_sill_{s}", gp, gq, 0.012, 0.01, "glow_amber", 0)
        # Trim down the inside of each pillar, and an amber marker at its foot.
        for nm, (a, b) in (("a", (fb[k], ft[k])), ("b", (sb[k], st[k]))):
            p, q = inset(a, b, 0.055)
            strut(f"canopy_trim_{nm}_{s}", p, q, 0.05, 0.03, "plastic", 0.008)
            p2, q2 = inset(a, b, 0.075)
            strut(f"canopy_led_{nm}_{s}", p2, p2.lerp(q2, 0.08), 0.012, 0.012, "led_amber", 0)
            strut(f"canopy_glow_{nm}_{s}", p2.lerp(q2, 0.14), p2.lerp(q2, 0.92), 0.014, 0.01, "glow_amber", 0)
    # Gussets across the windshield's corners, so its opening reads rounded.
    for k in (0, 1):
        strut(f"canopy_gusset_b{k}", fb[k].lerp(fb[1 - k], 0.12), fb[k].lerp(ft[k], 0.2), 0.1, 0.07,
              bev=0.02)
        strut(f"canopy_gusset_t{k}", ft[k].lerp(ft[1 - k], 0.12), ft[k].lerp(fb[k], 0.2), 0.1, 0.07,
              bev=0.02)
    # The roof over the pilot, from the B-pillars forward to the top of the windshield.
    slab("roof_front", [st[0], st[1], ft[1], ft[0]], 0.04, "paint", 0.004, inward=(0, 0.5, 5.0))


DESK_ASPECT = 3 / 8  # the desk instrument's surface is 8:3


def screen(name, width, loc, rot):
    h = width * (DESK_ASPECT if name == "screen_desk" else 9 / 16)
    c, r = SCREEN_CELLS[name]
    u0, u1 = c / 3, (c + 1.5 if name == "screen_desk" else c + 1) / 3
    q = quad(name, width, h, (0, 0, 0), (0, 0, 0), "screens", (u0, 1 - (r + 1) / 3, u1, 1 - r / 3))
    q["group"] = name
    m = Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()
    q.matrix_world = m
    # Bezel: a plastic frame just behind the screen, and a housing behind that.
    bz = box(f"{name}_bezel", (width + 0.05, 0.03, h + 0.05), (0, 0, 0), material="plastic",
             bev=0.008, segs=3)
    bz.matrix_world = m @ Matrix.Translation((0, 0.017, 0))
    if "overhead" not in name:
        hs = box(f"{name}_housing", (width + 0.08, 0.08, h + 0.08), (0, 0, 0),
                 material="paint_dark", bev=0.012, segs=2)
        hs.matrix_world = m @ Matrix.Translation((0, 0.07, 0))
    # A row of small soft keys under the screen.
    for i in range(5):
        k = box(f"{name}_key{i}", (width * 0.12, 0.012, 0.016), (0, 0, 0), material="plastic",
                bev=0.003)
        k.matrix_world = m @ Matrix.Translation(((i - 2) * width * 0.19, 0.0, -h / 2 - 0.016))
    led = box(f"{name}_led", (0.008, 0.008, 0.008), (0, 0, 0), material="led_amber", bev=0.002)
    led.matrix_world = m @ Matrix.Translation((width / 2 + 0.012, 0.0, -h / 2 - 0.012))


def button_grid(name, m, nx, ny, pitch, size=0.018, leds=True, toggles=False, seed=1):
    """A panel of buttons on a local x/z plane facing -y, placed by matrix m."""
    import random
    rnd = random.Random(seed)
    w, h = nx * pitch + 0.03, ny * pitch + 0.03
    p = box(f"{name}_plate", (w, 0.012, h), (0, 0, 0), material="plastic", bev=0.004)
    p.matrix_world = m @ Matrix.Translation((0, 0.006, 0))
    colours = ["led_amber"] * 6 + ["led_red", "led_green", "led_blue"]
    for j in range(ny):
        for i in range(nx):
            x = (i - (nx - 1) / 2) * pitch
            z = (j - (ny - 1) / 2) * pitch
            if toggles:
                base = cyl(f"{name}_tb{i}{j}", size * 0.35, 0.01, (0, 0, 0), material="paint_dark",
                           segs=12)
                base.matrix_world = m @ Matrix.Translation((x, -0.004, z)) @ Matrix.Rotation(
                    math.pi / 2, 4, "X")
                up = rnd.random() > 0.4
                lever = cyl(f"{name}_tl{i}{j}", size * 0.12, size * 1.1, (0, 0, 0),
                            material="plastic", segs=8)
                lever.matrix_world = m @ Matrix.Translation((x, -0.012 - size * 0.5, z)) @ (
                    Matrix.Rotation(math.pi / 2 + (0.45 if up else -0.45), 4, "X"))
                if leds:
                    l = box(f"{name}_tled{i}{j}", (0.006, 0.004, 0.006), (0, 0, 0),
                            material="led_amber" if up else "led_red", bev=0)
                    l.matrix_world = m @ Matrix.Translation((x, -0.002, z + pitch * 0.38))
            else:
                b = box(f"{name}_b{i}{j}", (size, 0.012, size * 0.8), (0, 0, 0),
                        material="plastic", bev=0.0025)
                b.matrix_world = m @ Matrix.Translation((x, -0.006, z))
                if leds and rnd.random() > 0.35:
                    l = box(f"{name}_l{i}{j}", (size * 0.6, 0.004, size * 0.18), (0, 0, 0),
                            material=rnd.choice(colours), bev=0)
                    l.matrix_world = m @ Matrix.Translation((x, -0.013, z + size * 0.18))


READOUT_COLS, READOUT_ROWS = 8, 16  # the readout atlas grid, as make_textures.py draws it


def readout(name, w, h, m, cell):
    """A small amber display: a recessed bezel and an emissive quad showing one cell of
    the readout atlas, on the local x/z plane of m facing -y."""
    c, r = cell % READOUT_COLS, (cell // READOUT_COLS) % READOUT_ROWS
    u0, u1 = c / READOUT_COLS, (c + 1) / READOUT_COLS
    v1, v0 = 1 - r / READOUT_ROWS, 1 - (r + 1) / READOUT_ROWS
    bz = box(f"{name}_bezel", (w + 0.012, 0.008, h + 0.012), (0, 0, 0), material="plastic",
             bev=0.002)
    bz.matrix_world = m @ Matrix.Translation((0, -0.002, 0))
    q = quad(name, w, h, (0, 0, 0), (0, 0, 0), "readout", (u0, v0, u1, v1))
    q.matrix_world = m @ Matrix.Translation((0, -0.0065, 0))


def live_panel(name, m, size):
    """A live display over leaf `name`, if live_panels.py lists it: a quad on the `screens`
    material showing its cell of the atlas, just in front of the readout or buttons, in its
    own node, `live_panels`. add_live_panels.py makes the same quads without Blender."""
    if name not in live_panels.PANELS:
        return
    q = quad(f"{name}_live", size[0], size[1], (0, 0, 0), (0, 0, 0), "screens", live_panels.uv(name))
    q["group"] = "live_panels"
    q.matrix_world = m @ Matrix.Translation((0, -live_panels.PANELS[name][2], 0))


def knob_row(name, m, w, n, rnd):
    for i in range(n):
        x = (i - (n - 1) / 2) * w / n
        k = cyl(f"{name}_k{i}", 0.009, 0.014, (0, 0, 0), material="plastic", segs=16, bev=0.002)
        k.matrix_world = m @ Matrix.Translation((x, -0.008, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X")
        d = box(f"{name}_kd{i}", (0.002, 0.003, 0.007), (0, 0, 0), material="led_amber", bev=0)
        d.matrix_world = m @ Matrix.Translation((x, -0.016, 0.004))


def greeble(name, m, w, h, rnd, depth=0):
    """Fills a w x h rectangle (local x/z of m, facing -y) with greebled sub-panels: split
    it a few times, then give each piece a readout, buttons, switches, knobs, a vent or a
    bolted plate. All parts sit on the -y side of m's plane."""
    if depth < 3 and max(w, h) > 0.16 and (depth < 1 or rnd.random() < 0.8):
        if w >= h:
            t = rnd.uniform(0.35, 0.65)
            wa, wb = w * t, w * (1 - t)
            greeble(f"{name}a", m @ Matrix.Translation((-w / 2 + wa / 2, 0, 0)), wa, h, rnd, depth + 1)
            greeble(f"{name}b", m @ Matrix.Translation((w / 2 - wb / 2, 0, 0)), wb, h, rnd, depth + 1)
        else:
            t = rnd.uniform(0.35, 0.65)
            ha, hb = h * t, h * (1 - t)
            greeble(f"{name}a", m @ Matrix.Translation((0, 0, -h / 2 + ha / 2)), w, ha, rnd, depth + 1)
            greeble(f"{name}b", m @ Matrix.Translation((0, 0, h / 2 - hb / 2)), w, hb, rnd, depth + 1)
        return
    gap = 0.008
    pw, ph = w - gap, h - gap
    # Every piece sits on its own slightly raised or sunk plate.
    lift = rnd.choice([0.004, 0.008, 0.012])
    plate = box(f"{name}_plate", (pw, lift, ph), (0, 0, 0),
                material=rnd.choice(["paint", "paint_dark", "paint_dark"]), bev=0.0025)
    plate.matrix_world = m @ Matrix.Translation((0, -lift / 2, 0))
    top = m @ Matrix.Translation((0, -lift, 0))
    corners = [top @ Vector((sx * pw / 2, 0, sz * ph / 2)) for sx, sz in
               [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    up = (m.to_3x3() @ Vector((0, -1, 0))).normalized()
    if min(pw, ph) > 0.05:
        bolts(f"{name}", corners, up, inset=0.01, r=0.0035, material="plastic")
    kind = rnd.random()
    iw, ih = pw - 0.03, ph - 0.03
    if iw < 0.03 or ih < 0.03:
        return
    if kind < 0.38:
        rw = min(iw, ih * 2.0)
        readout(f"{name}_ro", rw, rw / 2, top, rnd.randrange(READOUT_COLS * READOUT_ROWS))
        live_panel(name, top, (rw, rw / 2))
    elif kind < 0.66:
        pitch = rnd.choice([0.022, 0.026, 0.03])
        nx, ny = max(1, int(iw / pitch)), max(1, int(ih / pitch))
        button_grid(f"{name}_bt", top, nx, ny, pitch, size=pitch * 0.62,
                    seed=rnd.randrange(10 ** 6))
        live_panel(name, top, live_panels.button_size(nx, ny, pitch))
    elif kind < 0.78:
        pitch = 0.03
        nx, ny = max(1, int(iw / pitch)), max(1, int(ih / 0.05))
        button_grid(f"{name}_tg", top, nx, ny, pitch, size=0.02, toggles=True,
                    seed=rnd.randrange(10 ** 6))
    elif kind < 0.85:
        n = max(1, int(iw / 0.035))
        knob_row(f"{name}_kn", top, iw, n, rnd)
    elif kind < 0.91:
        v = box(f"{name}_vent", (iw, 0.004, ih), (0, 0, 0), material="hexpanel", bev=0.001)
        v.matrix_world = top @ Matrix.Translation((0, -0.002, 0))
    else:
        # A row of amber indicator slits.
        n = max(1, int(iw / 0.03))
        for i in range(n):
            l = box(f"{name}_sl{i}", (0.016, 0.004, 0.005), (0, 0, 0), material="led_amber", bev=0)
            l.matrix_world = top @ Matrix.Translation(((i - (n - 1) / 2) * iw / n, -0.002, 0))


def frame_matrix(loc, rot):
    return Matrix.Translation(Vector(loc)) @ Euler(
        [math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()


# The sloped button console under the monitors, as a (y, z) line.
SLOPE_A, SLOPE_B = (0.65, 0.62), (1.37, 0.79)


def slope_z(y):
    (y0, z0), (y1, z1) = SLOPE_A, SLOPE_B
    return z0 + (y - y0) * (z1 - z0) / (y1 - y0)


def build_console():
    GROUP[0] = "dashboard"
    rnd = random.Random(12)
    ang = math.degrees(math.atan2(SLOPE_B[1] - SLOPE_A[1], SLOPE_B[0] - SLOPE_A[0]))
    # The monitor bank: three equal screens in a row right under the windshield.
    box("monitor_bank", (0.66, 0.2, 0.24), (0, 1.56, 0.87), material="paint_dark", bev=0.01)
    for name, (w, loc, rot) in SCREENS.items():
        screen(name, w, loc, rot)
        if name in ("screen_center", "screen_left", "screen_right"):
            # A chunky moulded hood over each monitor, standing up into the windshield,
            # with an amber strip under its front edge.
            h = w * 9 / 16
            m = frame_matrix(loc, rot)
            hood = box(f"{name}_hood", (w + 0.11, 0.2, 0.05), (0, 0, 0), material="plastic",
                       bev=0.02, segs=4)
            hood.matrix_world = m @ Matrix.Translation((0, 0.045, h / 2 + 0.05))
            for side in (-1, 1):
                ear = box(f"{name}_ear{side}", (0.035, 0.16, h + 0.09), (0, 0, 0),
                          material="plastic", bev=0.014, segs=3)
                ear.matrix_world = m @ Matrix.Translation((side * (w / 2 + 0.04), 0.06, 0.005))
            led = box(f"{name}_hood_led", (w * 0.7, 0.006, 0.006), (0, 0, 0), material="led_amber",
                      bev=0)
            led.matrix_world = m @ Matrix.Translation((0, -0.05, h / 2 + 0.024))
    # The sloped console: a centre section ahead of the desk, and a wing each side that
    # reaches back past the desk toward the pilot.
    y_c = 1.10
    prism("console_centre", [(Y_NOSE, 0), (y_c, 0), (y_c, slope_z(y_c)), SLOPE_B,
                             (Y_NOSE, SLOPE_B[1])], "x", -0.45, 0.45, "paint", 0.008, 2)
    slope = lambda x, y: frame_matrix((x, y, slope_z(y) + 0.002), (-90 + ang, 0, 0))
    greeble("console_centre", slope(0, (y_c + SLOPE_B[0]) / 2 - 0.02), 0.86, 0.2, rnd)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        xa, xb = sorted((side * 0.45, side * 0.84))
        prism(f"console_wing_{s}", [(Y_NOSE, 0), (SLOPE_A[0], 0), SLOPE_A, SLOPE_B,
                                    (Y_NOSE, SLOPE_B[1])], "x", xa, xb, "paint", 0.008, 2)
        greeble(f"console_wing_{s}_fwd", slope(side * 0.645, 1.17), 0.36, 0.3, rnd)
        greeble(f"console_wing_{s}_aft", slope(side * 0.645, 0.85), 0.36, 0.3, rnd)
        box(f"console_wing_{s}_lip", (0.4, 0.03, 0.05), (side * 0.645, SLOPE_A[0], SLOPE_A[1] - 0.01),
            material="plastic", bev=0.012, segs=3)
        box(f"console_wing_{s}_glow", (0.34, 0.006, 0.008), (side * 0.645, SLOPE_A[0] - 0.016, SLOPE_A[1] - 0.03),
            material="glow_amber", bev=0)
        # The wing's face toward the pilot's knees.
        box(f"console_vent_{s}", (0.34, 0.012, 0.22), (side * 0.645, SLOPE_A[0] - 0.004, 0.3),
            material="hexpanel", bev=0.003)
    decal("serial", 0.3, (0, y_c - 0.001, 0.3), (0, 0, 0))
    decal("warn_eject", 0.24, (0, y_c - 0.001, 0.42), (0, 0, 0))
    # The desk: a tray reaching back from the console toward the pilot, carrying the
    # desk screen, on two arms so the floor under it stays clear.
    box("desk", (0.86, 0.36, 0.03), (0, 0.94, 0.63), (12, 0, 0), material="paint", bev=0.01,
        segs=3)
    box("desk_edge", (0.88, 0.04, 0.05), (0, 0.75, 0.585), (12, 0, 0), material="plastic",
        bev=0.015, segs=3)
    for side in (-1, 1):
        strut(f"desk_arm_{side}", (side * 0.34, 0.82, 0.52), (side * 0.34, 1.2, 0.4), 0.05, 0.06)
        box(f"desk_led_{side}", (0.09, 0.006, 0.01), (side * 0.3, 0.727, 0.585), (12, 0, 0),
            material="led_amber", bev=0)
        # Arm rests either side of the tray's near edge.
        box(f"arm_rest_{side}", (0.13, 0.24, 0.06), (side * 0.64, 0.58, 0.61), (12, 0, 0),
            material="leather", bev=0.025, segs=4)


def build_side_consoles():
    GROUP[0] = "side_consoles"
    xo_abs, xi_abs = WALL[1][0] - 0.02, 0.78
    rise = (0.78 - 0.66) / (xo_abs - 0.84)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        xo, xi = side * xo_abs, side * xi_abs
        prof = [(xo, 0), (xi, 0), (xi, 0.58), (side * 0.84, 0.66), (xo, 0.78)]
        if side > 0:
            prof = list(reversed(prof))
        prism(f"console_{s}", prof, "y", -0.70, 0.65, "paint", 0.01, 3)
        ang = math.degrees(math.atan(rise))
        top = lambda x, y: frame_matrix((side * x, y, 0.66 + (x - 0.84) * rise + 0.002),
                                        (-90, side * -ang, 0))
        rnd = random.Random(50 + side)
        greeble(f"console_{s}_aft", top(0.94, -0.3) @ Matrix.Translation((0, -0.001, 0)),
                0.17, 0.4, rnd)
        # The console's inner face, toward the pilot's legs: greebled too.
        greeble(f"console_{s}_face", frame_matrix((xi, -0.15, 0.3), (0, 0, -side * 90)), 1.0, 0.46,
                rnd)
        box(f"console_{s}_trim", (0.02, 1.1, 0.04), (xi + side * 0.005, -0.15, 0.56),
            material="plastic", bev=0.006)
        # A ledge along the cheek under the side window, from the console to the monitors.
        a = Vector((side * hull_x(0.65), 0.65, 0))
        b = Vector((side * hull_x(1.12), 1.12, 0))
        d = (b - a).normalized()
        inward = Vector((-side * d.y, side * d.x, 0)) * 1.0
        if inward.x * side > 0:
            inward = -inward
        c = (a + b) / 2 + inward * 0.06
        ledge = box(f"ledge_{s}", (0.13, (b - a).length, SILL_Z - 0.08), (0, 0, 0), material="paint_dark",
                    bev=0.012, segs=3)
        ledge.matrix_world = Matrix.Translation((c.x, c.y, (SILL_Z - 0.08) / 2)) @ (
            Vector((0, 1, 0)).rotation_difference(d).to_matrix().to_4x4())
        for i in range(3):
            p = a.lerp(b, 0.25 + i * 0.25) + inward * 0.06
            slot = box(f"ledge_{s}_slot{i}", (0.05, 0.14, 0.012), (0, 0, 0), material="plastic",
                       bev=0.004)
            slot.matrix_world = Matrix.Translation((p.x, p.y, SILL_Z - 0.076)) @ (
                Vector((0, 1, 0)).rotation_difference(d).to_matrix().to_4x4())
            led = box(f"ledge_{s}_led{i}", (0.012, 0.05, 0.006), (0, 0, 0), material="led_amber",
                      bev=0)
            led.matrix_world = Matrix.Translation((p.x, p.y, SILL_Z - 0.068)) @ (
                Vector((0, 1, 0)).rotation_difference(d).to_matrix().to_4x4())
        # The ledge's inner face, above the console wing: a strip of greebles.
        up = Vector((0, 0, 1))
        fy = -inward
        fx = fy.cross(up)
        fm = Matrix((fx, fy, up)).transposed().to_4x4()
        fm.translation = (a + b) / 2 + inward * 0.127 + up * (SILL_Z - 0.17)
        greeble(f"ledge_{s}_face", fm, 0.44, 0.14, rnd)
    # Throttle (left) and side stick (right).
    surface_z = lambda x: 0.66 + (x - 0.84) * rise
    tm = frame_matrix((-0.93, 0.15, surface_z(0.93) + 0.02), (0, 0, 0))
    base = box("throttle_base", (0.14, 0.3, 0.05), (0, 0, 0), material="paint_dark", bev=0.01)
    base.matrix_world = tm
    box("throttle_slot", (0.03, 0.24, 0.01), (0, 0, 0), material="plastic", bev=0).matrix_world = (
        tm @ Matrix.Translation((0, 0, 0.027)))
    # The lever is its own node and its own file (throttle.gltf), with its origin at the
    # hinge inside the base, so a scene can tilt it. It is built upright, mid-travel.
    GROUP[0] = "throttle"
    PIVOT[:] = tm.translation
    arm = box("throttle_arm", (0.03, 0.04, 0.17), (0, 0, 0), material="paint_dark", bev=0.008)
    arm.matrix_world = tm @ Matrix.Translation((0, 0, 0.085))
    grip = box("throttle_grip", (0.12, 0.08, 0.06), (0, 0, 0), material="plastic", bev=0.025, segs=4)
    grip.matrix_world = tm @ Matrix.Translation((0, 0, 0.19))
    GROUP[0] = "side_consoles"
    sm = frame_matrix((0.93, 0.15, surface_z(0.93) - 0.004), (0, 0, 0))
    b = cyl("stick_boot", 0.06, 0.05, (0, 0, 0), material="leather", segs=24)
    b.matrix_world = sm @ Matrix.Translation((0, 0, 0.025))
    sh = cyl("stick_shaft", 0.014, 0.18, (0, 0, 0), material="paint_dark", segs=16)
    sh.matrix_world = sm @ Matrix.Translation((0, 0, 0.12))
    g = box("stick_grip", (0.05, 0.06, 0.15), (0, 0, 0), material="plastic", bev=0.022, segs=4)
    g.matrix_world = sm @ Matrix.Translation((0, 0.005, 0.27)) @ Matrix.Rotation(-0.15, 4, "X")
    t = box("stick_trigger", (0.012, 0.02, 0.03), (0, 0, 0), material="led_red", bev=0.004)
    t.matrix_world = sm @ Matrix.Translation((0, 0.04, 0.3))
    for i in range(3):
        bt = cyl(f"stick_button{i}", 0.008, 0.012, (0, 0, 0), material="led_amber", segs=12)
        bt.matrix_world = sm @ Matrix.Translation(((i - 1) * 0.016, 0.0, 0.352))


def cable(name, points, r=0.008, material="plastic"):
    """A cable or hose through `points`, as a smooth curve swept by a circle, turned
    straight into a mesh."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 2
    cu.resolution_u = 8
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    cob = bpy.data.objects.new(name + "_curve", cu)
    bpy.context.collection.objects.link(cob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cob.evaluated_get(dg))
    bpy.data.objects.remove(cob)
    bpy.data.curves.remove(cu)
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    me.materials.clear()
    me.materials.append(mat(material))
    ob["group"] = GROUP[0]
    ALL.append(ob)
    return ob


def build_conduits():
    """Used-future clutter behind the pilot: cable looms sagging along the roof edges,
    conduit runs on the roof, and greebled roof and lower-wall panels."""
    GROUP[0] = "conduits"
    rnd = random.Random(91)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        ribs = [Y_BACK + 0.05, -0.6, Y_FRONT - 0.08]
        for c, (dx, dz, r) in enumerate([(0.0, 0.0, 0.012), (0.03, -0.01, 0.008),
                                         (-0.02, -0.025, 0.01), (0.015, -0.03, 0.006)]):
            x = side * (WALL[-1][0] - 0.07 + dx)
            pts = []
            for a, b in zip(ribs, ribs[1:]):
                pts.append((x, a, CEIL_Z - 0.05 + dz))
                pts.append((x - side * 0.01, (a + b) / 2, CEIL_Z - 0.1 + dz - rnd.uniform(0, 0.04)))
            pts.append((x, ribs[-1], CEIL_Z - 0.05 + dz))
            cable(f"loom_{s}{c}", pts, r, rnd.choice(["plastic", "plastic", "leather", "paint_dark"]))
        # Greebled lower walls behind the consoles' ends.
        m = frame_matrix((side * (wall_x(0.6) - 0.03), (Y_BACK - 0.70) / 2, 0.55),
                         (0, 0, -side * 90))
        greeble(f"lowwall_{s}", m, -0.70 - Y_BACK - 0.08, 0.6, rnd)
    for k, (x, r) in enumerate([(-0.08, 0.022), (0.0, 0.016), (0.07, 0.026)]):
        cyl(f"roof_conduit{k}", r, Y_FRONT - Y_BACK - 0.2, (x, (Y_FRONT + Y_BACK) / 2 - 0.05, CEIL_Z - 0.07),
            (90, 0, 0), "paint_dark" if k != 1 else "plastic", 16)
    for y in (-0.95, -0.35):
        box(f"roof_clamp_{y}", (0.26, 0.04, 0.03), (0, y, CEIL_Z - 0.07), material="paint", bev=0.005)
    for j, (ya, yb) in enumerate([(Y_BACK + 0.05, -0.64), (-0.56, Y_FRONT - 0.05)]):
        for side in (-1, 1):
            m = frame_matrix((side * 0.47, (ya + yb) / 2, CEIL_Z - 0.026), (90, 0, 0))
            greeble(f"roof_{j}{side}", m, 0.28, yb - ya - 0.04, rnd)


def build_header():
    """The overhead console: a wedge across the top of the windshield whose face is
    tilted at the pilot's eyes, with a screen set into it each side, a switch panel
    between them and a lamp under it."""
    GROUP[0] = "header"
    rnd = random.Random(31)
    prism("overhead", [(0.58, CEIL_Z + 0.01), (0.58, 1.83), (0.714, 1.607), (0.86, 1.607),
                       (0.92, CEIL_Z + 0.01)], "x", -0.68, 0.68, "paint", 0.012, 3)
    greeble("overhead_mid", frame_matrix((0, 0.645, 1.72), (31, 0, 0)), 0.34, 0.2, rnd)
    box("overhead_lamp", (0.16, 0.05, 0.012), (0, 0.79, 1.603), material="led_amber", bev=0.004)
    for side in (-1, 1):
        box(f"overhead_glow_{side}", (0.4, 0.02, 0.008), (side * 0.4, 0.79, 1.604),
            material="glow_amber", bev=0)


# ---------------------------------------------------------------------------- finishing

def finish():
    """Applies modifiers, bakes transforms, smooths by angle, box-projects coordinates."""
    dg = bpy.context.evaluated_depsgraph_get()
    for ob in list(ALL):
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.transform(ob.matrix_world)
        keep = bool(ob.get("keep_uv", False))
        material = ob.data.materials[0].name
        ob.modifiers.clear()
        old = ob.data
        ob.data = me
        ob.matrix_world = Matrix.Identity(4)
        if old.users == 0:
            bpy.data.meshes.remove(old)
        if not me.materials:
            me.materials.append(mat(material))
        bm = bmesh.new()
        bm.from_mesh(me)
        uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
        if not keep:
            tile = TILE.get(material, 1.0)
            for f in bm.faces:
                n = f.normal
                ax = max(range(3), key=lambda i: abs(n[i]))
                for loop in f.loops:
                    co = loop.vert.co
                    if ax == 0:
                        u, v = co.y * (1 if n.x > 0 else -1), co.z
                    elif ax == 1:
                        u, v = co.x * (-1 if n.y > 0 else 1), co.z
                    else:
                        u, v = co.x, co.y * (1 if n.z > 0 else -1)
                    loop[uvl].uv = (u / tile, v / tile)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
    bpy.ops.object.select_all(action="DESELECT")
    for ob in ALL:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = ALL[0]
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
    # One node per group, so the file has a handful of named parts, not hundreds.
    groups = {}
    for ob in ALL:
        groups.setdefault(ob["group"], []).append(ob)
    joined = []
    for name, obs in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for ob in obs:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        if len(obs) > 1:
            bpy.ops.object.join()
        obs[0].name = name
        obs[0].data.name = name
        joined.append(obs[0])
    ALL[:] = joined
    # The throttle lever: mesh moved so its origin is the hinge, object placed back there.
    lever = next(o for o in ALL if o.name == "throttle")
    lever.data.transform(Matrix.Translation(-Vector(PIVOT)))
    lever.location = PIVOT
    lo = [min(v.co[i] for v in lever.data.vertices) for i in range(3)]
    hi = [max(v.co[i] for v in lever.data.vertices) for i in range(3)]
    print("throttle pivot (blender)", [round(c, 4) for c in PIVOT],
          "bounds centre from pivot", [round((a + b) / 2, 4) for a, b in zip(lo, hi)],
          "size", [round(b - a, 4) for a, b in zip(lo, hi)])


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build_shell()
    build_rear()
    build_nose()
    build_console()
    build_side_consoles()
    build_header()
    build_conduits()
    finish()
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in ALL)
    print(f"objects {len(ALL)}  triangles {tris}")
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    lever = next(o for o in ALL if o.name == "throttle")
    for path, obs in [(OUT, [o for o in ALL if o is not lever]),
                      (os.path.join(os.path.dirname(OUT), "throttle.gltf"), [lever])]:
        bpy.ops.object.select_all(action="DESELECT")
        for ob in obs:
            ob.select_set(True)
        if obs == [lever]:
            lever.location = (0, 0, 0)
        bpy.ops.export_scene.gltf(
            filepath=path,
            use_selection=True,
            export_format="GLTF_SEPARATE",
            export_image_format="NONE",
            export_tangents=True,
            export_apply=True,
            export_yup=True,
            export_cameras=False,
            export_lights=False,
            export_materials="EXPORT",
            export_vertex_color="NONE",
        )


main()
