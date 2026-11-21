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
import sys

import bpy  # first: it makes bmesh and mathutils importable
import bmesh
from mathutils import Euler, Matrix, Vector

# Texture tile sizes in metres per repeat, per tiling material.
TILE = {
    "paint": 0.5,
    "paint_dark": 0.5,
    "floor": 0.6,
    "leather": 0.3,
    "plastic": 0.4,
    "hexpanel": 0.5,
}
SETS = {  # material -> texture set
    "paint": "paint",
    "paint_dark": "paint",
    "floor": "floor",
    "leather": "leather",
    "plastic": "plastic",
    "hexpanel": "hexpanel",
}
NORMAL_SCALE = {"plastic": 0.35, "paint": 0.6, "paint_dark": 0.6}
SCREENS = {
    # name: (width m, centre, euler degrees (x tilt, y, z yaw))
    "screen_center": (0.72, (0.0, 1.44, 0.94), (-14, 0, 0)),
    "screen_left": (0.50, (-0.66, 1.36, 0.90), (-14, 0, 30)),
    "screen_right": (0.50, (0.66, 1.36, 0.90), (-14, 0, -30)),
    "screen_side_left": (0.30, (-0.98, 0.86, 0.86), (-50, 0, 58)),
    "screen_side_right": (0.30, (0.98, 0.86, 0.86), (-50, 0, -58)),
    # Lying on the desk in front of the pilot, its far edge raised a little.
    # The instrument's playing surface: 8:3, not 16:9 (see DESK_ASPECT).
    "screen_desk": (0.72, (0.0, 0.70, 0.66), (-78, 0, 0)),
}
LEDS = {
    "led_green": (0.15, 1.0, 0.35),
    "led_amber": (1.0, 0.55, 0.05),
    "led_red": (1.0, 0.08, 0.05),
    "led_blue": (0.15, 0.55, 1.0),
    "light_strip": (0.85, 0.92, 1.0),
}

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
    elif name.startswith("screen_"):
        c = tex(f"{TEX}/{name}.jpg")
        em = nt.nodes.new("ShaderNodeEmission")
        link(c.outputs["Color"], em.inputs["Color"])
        em.inputs["Strength"].default_value = 1.0
        link(em.outputs["Emission"], out.inputs["Surface"])
    elif name in LEDS:
        col = LEDS[name]
        bsdf.inputs["Base Color"].default_value = (*[c * 0.3 for c in col], 1)
        bsdf.inputs["Emission Color"].default_value = (*col, 1)
        bsdf.inputs["Emission Strength"].default_value = 2.5 if name == "light_strip" else 5.0
        bsdf.inputs["Roughness"].default_value = 0.35
    elif name == "readout":
        c = tex(f"{TEX}/readouts.png")
        bsdf.inputs["Base Color"].default_value = (0.01, 0.01, 0.01, 1)
        link(c.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.0
        bsdf.inputs["Roughness"].default_value = 0.2
    elif name == "glass":
        bsdf.inputs["Base Color"].default_value = (0.55, 0.65, 0.75, 1)
        bsdf.inputs["Roughness"].default_value = 0.04
        bsdf.inputs["Alpha"].default_value = 0.10
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

# Wall cross-section (x, z) for the right side; the left mirrors it.
WALL = [(1.36, 0.0), (1.36, 0.85), (1.27, 1.65), (1.06, 2.16)]
CEIL_Z = 2.16
Y_BACK, Y_FRONT, Y_NOSE = -1.70, 1.25, 2.02
WIN_BOTTOM_Z = 1.16
WIN_SIDE_Y = -0.15  # the side windows run from here forward to the windshield


def wall_x(z):
    for (x0, z0), (x1, z1) in zip(WALL, WALL[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return x0 + (x1 - x0) * t
    return WALL[-1][0]


def nose_y(z):
    """The windshield plane: y where it meets height z (it leans back as it rises)."""
    if z <= WIN_BOTTOM_Z:
        return Y_NOSE
    t = (z - WIN_BOTTOM_Z) / (CEIL_Z - WIN_BOTTOM_Z)
    return Y_NOSE + (Y_FRONT - Y_NOSE) * t


def build_shell():
    GROUP[0] = "cabin"
    # A dark backing shell behind the wall panels, so the seams between them read dark.
    # Above the sill it stops where the side windows start.
    for side in (-1, 1):
        prof = [(side * (x + 0.04), z) for x, z in WALL]
        for i, ((x0, z0), (x1, z1)) in enumerate(zip(prof, prof[1:])):
            y1 = Y_FRONT if i == 0 else WIN_SIDE_Y
            slab(
                f"shell_{'L' if side < 0 else 'R'}{i}",
                [(x0, Y_BACK, z0), (x0, y1, z0), (x1, y1, z1), (x1, Y_BACK, z1)],
                0.02, "paint_dark", 0, inward=(0, 0, 1.0),
            )
    slab("shell_spine", [(-0.37, 0.6, CEIL_Z + 0.04), (0.37, 0.6, CEIL_Z + 0.04),
                         (0.37, Y_FRONT, CEIL_Z + 0.04), (-0.37, Y_FRONT, CEIL_Z + 0.04)],
         0.02, "paint_dark", 0, inward=(0, 0, 0))
    slab("shell_ceiling", [(-1.1, Y_BACK, CEIL_Z + 0.04), (1.1, Y_BACK, CEIL_Z + 0.04),
                           (1.1, 0.6, CEIL_Z + 0.04), (-1.1, 0.6, CEIL_Z + 0.04)],
         0.02, "paint_dark", 0, inward=(0, 0, 0))

    # Wall panels: between the ribs, one per profile segment, inset from each other.
    ribs = [Y_BACK, -0.95, -0.15, 0.62, Y_FRONT]
    gap = 0.008
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        for j, (ya, yb) in enumerate(zip(ribs, ribs[1:])):
            for i, ((x0, z0), (x1, z1)) in enumerate(zip(WALL, WALL[1:])):
                d0 = Vector((x1 - x0, z1 - z0)).normalized() * gap
                if i >= 1 and ya >= WIN_SIDE_Y - 1e-6:
                    # Side windows: glass between the ribs, from the sill to the roof.
                    slab(f"side_glass_{s}{j}{i}",
                         [(side * x0, ya, z0), (side * x0, yb, z0), (side * x1, yb, z1),
                          (side * x1, ya, z1)], 0.006, "glass", 0, inward=(side * 3.0, 0, 1.0))
                    continue
                material = "hexpanel" if (i == 1 and j == 0) else "paint"
                slab(
                    f"wall_{s}{j}{i}",
                    [
                        (side * (x0 + d0.x), ya + gap, z0 + d0.y),
                        (side * (x0 + d0.x), yb - gap, z0 + d0.y),
                        (side * (x1 - d0.x), yb - gap, z1 - d0.y),
                        (side * (x1 - d0.x), ya + gap, z1 - d0.y),
                    ],
                    0.025, material, 0.005, inward=(side * 3.0, (ya + yb) / 2, (z0 + z1) / 2),
                )
                # Inward normal: across the segment, toward the cabin's centre.
                n = Vector((-(z1 - z0), 0, x1 - x0)).normalized()
                n = Vector((side * n.x, 0, n.z))
                if n.dot(Vector((-side, 0, 0.3))) < 0:
                    n = -n
                if material == "paint":
                    bolts(f"wall_{s}{j}{i}",
                          [(side * x0, ya, z0), (side * x0, yb, z0), (side * x1, yb, z1),
                           (side * x1, ya, z1)], n, inset=0.035)
        # Window frame: a sill under the side glass and a transom where the wall bends.
        for k, (x, z, th) in enumerate([(WALL[1][0], WALL[1][1], 0.07), (WALL[2][0], WALL[2][1], 0.05)]):
            box(f"window_frame_{s}{k}", (0.07, Y_FRONT - WIN_SIDE_Y + 0.06, th),
                (side * (x - 0.02), (Y_FRONT + WIN_SIDE_Y) / 2, z), material="paint_dark",
                bev=0.008)
        # Ribs: a frame member over each panel join, wall and ceiling, and a pillar where
        # the side glass meets the windshield.
        for j, y in enumerate(ribs[1:]):
            for i, ((x0, z0), (x1, z1)) in enumerate(zip(WALL, WALL[1:])):
                slab(
                    f"rib_{s}{j}{i}",
                    [(side * (x0 - 0.02), y - 0.03, z0), (side * (x0 - 0.02), y + 0.03, z0),
                     (side * (x1 - 0.02), y + 0.03, z1), (side * (x1 - 0.02), y - 0.03, z1)],
                    0.05, "paint_dark", 0.008, inward=(0, y, 1.0),
                )
    for j, y in enumerate(ribs[1:]):
        box(f"rib_ceiling{j}", (2.12, 0.06, 0.05), (0, y, CEIL_Z - 0.025), material="paint_dark")

    # Ceiling: two light panels with a hex vent between, and light strips along the edges.
    for j, (ya, yb) in enumerate(zip(ribs, ribs[1:])):
        for k, (xa, xb) in enumerate([(-1.06, -0.36), (-0.36, 0.36), (0.36, 1.06)]):
            m = "hexpanel" if k == 1 and j in (1, 2) else "paint"
            if j == 3 and k != 1:
                # Over the pilot the roof's outer panels are glass, up to the windshield.
                m = "glass"
            box(f"ceiling_{j}{k}", (xb - xa - 0.012, yb - ya - 0.012, 0.025),
                ((xa + xb) / 2, (ya + yb) / 2, CEIL_Z - 0.0125), material=m, bev=0.004)
        for side in (-1, 1):
            if j == 3:
                continue
            box(f"light_strip_{j}{side}", (0.05, yb - ya - 0.2, 0.02),
                (side * 0.9, (ya + yb) / 2, CEIL_Z - 0.035), material="light_strip", bev=0.004)

    # Floor: diamond plate in two halves, a dark seam and a raised centre walkway edge.
    for k, (ya, yb) in enumerate([(Y_BACK, 0.2), (0.2, Y_NOSE)]):
        box(f"floor_{k}", (2.72, yb - ya - 0.01, 0.03), (0, (ya + yb) / 2, -0.015),
            material="floor", bev=0.003)
    for side in (-1, 1):
        box(f"floor_kick_{side}", (0.06, Y_NOSE - Y_BACK, 0.10),
            (side * 1.31, (Y_NOSE + Y_BACK) / 2, 0.05), material="paint_dark")
    decal("stripe", 1.4, (0, -1.35, 0.002), (-90, 0, 0), name="decal_stripe_floor", repeat=4)
    decal("deck_number", 0.4, (0.75, -1.05, 0.002), (-90, 0, 0))
    decal("arrow", 0.3, (-0.75, -1.05, 0.002), (-90, 0, 0))

    # Pipes along both walls, with clamps.
    for side in (-1, 1):
        for z, r in [(0.22, 0.028), (0.30, 0.018)]:
            x = side * (wall_x(z) - 0.08)
            cyl(f"pipe_{side}_{z}", r, Y_FRONT - Y_BACK - 0.1, (x, (Y_FRONT + Y_BACK) / 2, z),
                (90, 0, 0), "paint_dark", 20)
        for y in (-1.3, -0.55, 0.25, 1.0):
            box(f"clamp_{side}_{y}", (0.06, 0.04, 0.16), (side * (wall_x(0.26) - 0.07), y, 0.26),
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
    cutter = box("_cut", (0.84, 0.4, 1.84), (0, Y_BACK, 0.98), material="paint", bev=0)
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
    box("hatch_frame_top", (1.0, 0.1, 0.08), (0, Y_BACK + 0.02, 1.94), material="paint_dark")
    for side in (-1, 1):
        box(f"hatch_frame_{side}", (0.08, 0.1, 1.9), (side * 0.46, Y_BACK + 0.02, 0.95),
            material="paint_dark")
    box("hatch_door", (0.84, 0.04, 1.84), (0, Y_BACK - 0.04, 0.98), material="hexpanel", bev=0.01)
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
    decal("warn_hatch", 0.6, (0, Y_BACK + 0.012, 1.55), (0, 0, 180), name="decal_warn_hatch")
    for side in (-1, 1):
        decal("stripe", 1.8, (side * 0.53, Y_BACK + 0.012, 0.95), (0, 90, 180),
              name=f"decal_stripe_hatch_{side}", repeat=6)
        box(f"rear_light_{side}", (0.06, 0.03, 0.3), (side * 0.75, Y_BACK + 0.015, 1.6),
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


# The canopy, above the sill. In plan the nose tapers in from the side walls to the
# windshield, and the windshield rakes back to meet the roof well behind its base.
SILL_Z = WIN_BOTTOM_Z
CANOPY_FRONT_Y = 2.45     # the windshield's base
CANOPY_HALF_W = 0.86      # half its width at the base
CANOPY_TOP_Y = 1.5        # where it meets the roof
CANOPY_TOP_HALF_W = 0.62  # half its width there


def build_nose():
    GROUP[0] = "windshield"
    # Below the sill the hull stays square: opaque cheeks and a front wall, mostly hidden
    # by the dashboard.
    zs = sorted({z for _, z in WALL if z <= SILL_Z} | {SILL_Z})
    for side in (-1, 1):
        for i, (z0, z1) in enumerate(zip(zs, zs[1:])):
            x0, x1 = side * wall_x(z0), side * wall_x(z1)
            slab(f"cheek_{side}{i}", [(x0, Y_FRONT, z0), (x0, Y_NOSE, z0), (x1, Y_NOSE, z1),
                                      (x1, Y_FRONT, z1)], 0.03, "paint", 0.004,
                 inward=(side * 3.0, Y_FRONT, 0.5))
    slab("nose_lower", [(-wall_x(0), Y_NOSE, 0), (wall_x(0), Y_NOSE, 0),
                        (wall_x(SILL_Z), Y_NOSE, SILL_Z), (-wall_x(SILL_Z), Y_NOSE, SILL_Z)],
         0.04, "paint_dark", 0.004, inward=(0, 3.0, 0.5))
    # The glareshield: a deck at the sill, from behind the screens out to the glass.
    xs = wall_x(SILL_Z)
    prism("glareshield", [(-xs - 0.02, 1.6), (xs + 0.02, 1.6), (xs + 0.02, Y_NOSE + 0.05),
                          (CANOPY_HALF_W + 0.12, CANOPY_FRONT_Y + 0.1),
                          (-CANOPY_HALF_W - 0.12, CANOPY_FRONT_Y + 0.1), (-xs - 0.02, Y_NOSE + 0.05)],
          "y", 0, 1, "paint_dark", 0.006, 2)
    g = ALL[-1]
    # prism() extrudes along y from an (x, z) profile; here the profile is a plan outline,
    # so stand it up: (x, y, z) <- (x, z, y scaled to the deck's thickness).
    for v in g.data.vertices:
        x, y, z = v.co
        v.co = (x, z, SILL_Z - 0.05 + y * 0.05)
    bm = bmesh.new()
    bm.from_mesh(g.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(g.data)
    bm.free()
    lip = strut("glareshield_lip", (-xs, 1.6, SILL_Z + 0.01), (xs, 1.6, SILL_Z + 0.01), 0.04, 0.05,
                "plastic", 0.012)

    # The glass: one big raked windshield, and a corner pane each side joining it to the
    # side windows.
    fb = [Vector((s * CANOPY_HALF_W, CANOPY_FRONT_Y, SILL_Z)) for s in (-1, 1)]
    ft = [Vector((s * CANOPY_TOP_HALF_W, CANOPY_TOP_Y, CEIL_Z)) for s in (-1, 1)]
    pane("glass_front", [fb[0], fb[1], ft[1], ft[0]])
    strut("canopy_sill_front", fb[0], fb[1], 0.06, 0.05)
    strut("canopy_top_front", ft[0], ft[1], 0.06, 0.06)
    for k, side in enumerate((-1, 1)):
        s = "L" if side < 0 else "R"
        wb = Vector((side * wall_x(SILL_Z), Y_FRONT, SILL_Z))
        wm = Vector((side * WALL[2][0], Y_FRONT, WALL[2][1]))
        wt = Vector((side * WALL[3][0], Y_FRONT, CEIL_Z))
        # Split at the wall's bend so the corner glass meets the side window's two facets.
        mid = fb[k].lerp(ft[k], (WALL[2][1] - SILL_Z) / (CEIL_Z - SILL_Z))
        pane(f"glass_corner_{s}_lower", [wb, fb[k], mid, wm])
        pane(f"glass_corner_{s}_upper", [wm, mid, ft[k], wt])
        strut(f"canopy_pillar_{s}", fb[k], ft[k], 0.055, 0.06)
        strut(f"canopy_sill_{s}", wb, fb[k], 0.06, 0.05)
        strut(f"canopy_top_{s}", wt, ft[k], 0.06, 0.06)
        strut(f"canopy_transom_{s}", wm, mid, 0.035, 0.04)
        # The cheek's short glass strip between the side window's sill and the canopy's.
        x0, x1 = side * wall_x(WALL[1][1]), side * wall_x(SILL_Z)
    # The roof runs forward to the top of the windshield.
    slab("roof_front", [(-WALL[3][0], Y_FRONT - 0.02, CEIL_Z), (WALL[3][0], Y_FRONT - 0.02, CEIL_Z),
                        (CANOPY_TOP_HALF_W, CANOPY_TOP_Y, CEIL_Z),
                        (-CANOPY_TOP_HALF_W, CANOPY_TOP_Y, CEIL_Z)], 0.04, "paint_dark", 0.004,
         inward=(0, 1.3, 5.0))


DESK_ASPECT = 3 / 8  # the desk instrument's surface is 8:3


def screen(name, width, loc, rot):
    h = width * (DESK_ASPECT if name == "screen_desk" else 9 / 16)
    q = quad(name, width, h, (0, 0, 0), (0, 0, 0), name)
    q["group"] = name
    m = Matrix.Translation(Vector(loc)) @ Euler([math.radians(a) for a in rot], "XYZ").to_matrix().to_4x4()
    q.matrix_world = m
    # Bezel: a plastic frame just behind the screen, and a housing behind that.
    bz = box(f"{name}_bezel", (width + 0.05, 0.03, h + 0.05), (0, 0, 0), material="plastic",
             bev=0.008, segs=3)
    bz.matrix_world = m @ Matrix.Translation((0, 0.017, 0))
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
    elif kind < 0.66:
        pitch = rnd.choice([0.022, 0.026, 0.03])
        nx, ny = max(1, int(iw / pitch)), max(1, int(ih / pitch))
        button_grid(f"{name}_bt", top, nx, ny, pitch, size=pitch * 0.62,
                    seed=rnd.randrange(10 ** 6))
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


def build_console():
    GROUP[0] = "dashboard"
    # Main dashboard: an extruded profile across the cabin, (y, z).
    xw = wall_x(0.7) - 0.02
    prism("dash_body", [(Y_NOSE, 0), (1.18, 0), (1.18, 0.48), (1.04, 0.54), (1.04, 0.62),
                        (1.22, 0.67), (Y_NOSE, 0.74)], "x", -xw, xw, "paint", 0.01, 3)
    prism("dash_lip", [(1.0, 0.6), (1.06, 0.6), (1.06, 0.66), (1.0, 0.66)], "x", -xw + 0.05,
          xw - 0.05, "plastic", 0.012, 3)
    # Monitor deck behind the screens.
    prism("dash_deck", [(1.3, 0.665), (Y_NOSE, 0.74), (Y_NOSE, 1.06), (1.74, 1.06), (1.6, 0.7)],
          "x", -xw + 0.1, xw - 0.1, "paint_dark", 0.01, 2)
    for name, (w, loc, rot) in SCREENS.items():
        screen(name, w, loc, rot)
    # The desk: a shelf reaching back from the dash toward the pilot, carrying the desk
    # screen, on two arms so the floor under it stays clear.
    box("desk", (0.86, 0.6, 0.03), (0, 0.72, 0.6), (12, 0, 0), material="paint_dark", bev=0.01,
        segs=3)
    box("desk_edge", (0.9, 0.04, 0.05), (0, 0.415, 0.545), (12, 0, 0), material="plastic",
        bev=0.015, segs=3)
    for side in (-1, 1):
        strut(f"desk_arm_{side}", (side * 0.34, 0.5, 0.5), (side * 0.34, 1.18, 0.36), 0.05, 0.06)
        for i in range(4):
            box(f"desk_key_{side}{i}", (0.045, 0.03, 0.012), (side * 0.385, 0.52 + i * 0.07,
                0.585 + i * 0.0148), (12, 0, 0), material="led_amber" if i % 2 else "plastic",
                bev=0.003)
    # Greebled banks across the dash top, between the lip and the screens.
    rnd = random.Random(12)
    for side in (-1, 1):
        greeble(f"dash_top_{side}", frame_matrix((side * 0.78, 1.15, 0.648), (-75, 0, 0)), 0.76,
                0.17, rnd)
    greeble("dash_top_mid", frame_matrix((0, 1.15, 0.648), (-75, 0, 0)), 0.78, 0.17, rnd)
    for side in (-1, 1):
        box(f"dash_vent_{side}", (0.5, 0.012, 0.22), (side * 0.6, 1.18, 0.26), material="hexpanel",
            bev=0.003)
        bolts(f"dash_vent_{side}", [(side * 0.6 + sx * 0.25, 1.174, 0.26 + sz * 0.11)
                                    for sx, sz in [(-1, -1), (1, -1), (1, 1), (-1, 1)]],
              (0, -1, 0), inset=0.015, r=0.005)
    decal("serial", 0.3, (0, 1.181, 0.3), (0, 0, 0))
    decal("warn_eject", 0.24, (0, 1.181, 0.42), (0, 0, 0))
    for side in (-1, 1):
        decal("stripe", 0.5, (side * 0.6, 1.035, 0.58), (0, 0, 0), name=f"decal_stripe_lip_{side}",
              repeat=2.5)


def build_side_consoles():
    GROUP[0] = "side_consoles"
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        xo, xi = side * (wall_x(0.8) - 0.01), side * 0.62
        prof = [(xo, 0), (xi, 0), (xi, 0.58), (side * 0.74, 0.66), (xo, 0.78)]
        if side > 0:
            prof = list(reversed(prof))
        prism(f"console_{s}", prof, "y", -0.75, 1.18, "paint", 0.01, 3)
        # Top-panel tilt: rising toward the wall.
        ang = math.degrees(math.atan2(0.78 - 0.66, abs(xo) - 0.74))
        top = lambda x, y: frame_matrix((side * x, y, 0.66 + (x - 0.74) * math.tan(math.radians(ang)) + 0.002),
                                        (-90, side * -ang, 0))
        # The top: greebled panels before and behind the throttle / stick, a label at the
        # back. Each side gets its own pattern.
        rnd = random.Random(50 + side)
        greeble(f"console_{s}_aft", top(1.03, -0.47) @ Matrix.Translation((0, -0.001, 0)),
                0.5, 0.44, rnd)
        greeble(f"console_{s}_fwd", top(1.03, 0.4) @ Matrix.Translation((0, -0.001, 0)),
                0.5, 0.56, rnd)
        decal("label_power" if side < 0 else "label_shields", 0.12, (0, 0, 0), (0, 0, 0),
              name=f"decal_label_{s}")
        ALL[-1].matrix_world = top(0.86, -0.15) @ Matrix.Translation((0, -0.003, 0))
        # The console's inner face, toward the pilot's legs: greebled too.
        greeble(f"console_{s}_face", frame_matrix((xi, 0.2, 0.3), (0, 0, -side * 90)), 1.7, 0.46,
                rnd)
        box(f"console_{s}_trim", (0.02, 1.9, 0.04), (xi + side * 0.005, 0.21, 0.56),
            material="plastic", bev=0.006)
    # Throttle (left) and side stick (right).
    xo = wall_x(0.8) - 0.01
    surface_z = lambda x: 0.66 + (x - 0.74) * (0.78 - 0.66) / (xo - 0.74)
    tm = frame_matrix((-0.95, -0.1, surface_z(0.95) + 0.02), (0, 0, 0))
    base = box("throttle_base", (0.16, 0.3, 0.05), (0, 0, 0), material="paint_dark", bev=0.01)
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
    sm = frame_matrix((0.95, -0.1, surface_z(0.95) - 0.004), (0, 0, 0))
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
    """Used-future clutter: cable looms sagging along the roof edges and down the window
    pillars, conduit runs on the roof, and greebled roof and lower-wall panels."""
    GROUP[0] = "conduits"
    rnd = random.Random(91)
    for side in (-1, 1):
        s = "L" if side < 0 else "R"
        # Looms along the roof edge, sagging between the ribs.
        ribs = [Y_BACK + 0.05, -0.95, -0.15, 0.62, Y_FRONT - 0.05]
        for c, (dx, dz, r) in enumerate([(0.0, 0.0, 0.012), (0.03, -0.01, 0.008),
                                         (-0.02, -0.025, 0.01), (0.015, -0.03, 0.006)]):
            x = side * (WALL[3][0] - 0.06 + dx)
            pts = []
            for a, b in zip(ribs, ribs[1:]):
                pts.append((x, a, CEIL_Z - 0.05 + dz))
                pts.append((x - side * 0.01, (a + b) / 2, CEIL_Z - 0.1 + dz - rnd.uniform(0, 0.04)))
            pts.append((x, ribs[-1], CEIL_Z - 0.05 + dz))
            cable(f"loom_{s}{c}", pts, r, rnd.choice(["plastic", "plastic", "leather", "paint_dark"]))
        # Cables down the pillar where the side glass meets the windshield.
        for c in range(3):
            x0 = side * (wall_x(2.0) - 0.05 - c * 0.018)
            pts = [(x0, Y_FRONT - 0.06, 2.05), (side * (wall_x(1.5) - 0.06 - c * 0.018), Y_FRONT - 0.07, 1.5),
                   (side * (wall_x(0.95) - 0.07 - c * 0.018), Y_FRONT - 0.06, 0.95)]
            cable(f"pillar_{s}{c}", pts, 0.007, "plastic")
        # Greebled lower walls behind the consoles' ends, and roof side panels.
        # (Only behind the consoles: further forward they cover the wall.)
        m = frame_matrix((side * (wall_x(0.6) - 0.03), (Y_BACK - 0.78) / 2, 0.6),
                         (0, 0, -side * 90))
        greeble(f"lowwall_{s}", m, -0.78 - Y_BACK - 0.08, 0.45, rnd)
    # Roof: two conduit runs down the middle with clamps, and greebled roof panels.
    for k, (x, r) in enumerate([(-0.08, 0.022), (0.0, 0.016), (0.07, 0.026)]):
        cyl(f"roof_conduit{k}", r, Y_FRONT - Y_BACK - 0.4, (x, (Y_FRONT + Y_BACK) / 2 - 0.1, CEIL_Z - 0.07),
            (90, 0, 0), "paint_dark" if k != 1 else "plastic", 16)
    for y in (-1.3, -0.55, 0.25, 0.95):
        box(f"roof_clamp_{y}", (0.26, 0.04, 0.03), (0, y, CEIL_Z - 0.07), material="paint", bev=0.005)
    for j, (ya, yb) in enumerate([(Y_BACK + 0.05, -0.98), (-0.92, -0.18), (-0.12, 0.59)]):
        for side in (-1, 1):
            m = frame_matrix((side * 0.62, (ya + yb) / 2, CEIL_Z - 0.026), (90, 0, 0))
            greeble(f"roof_{j}{side}", m, 0.42, yb - ya - 0.04, rnd)


def build_header():
    """A lit header under the roof, just behind the top of the windshield."""
    GROUP[0] = "header"
    rnd = random.Random(31)
    y = CANOPY_TOP_Y - 0.16
    prism("header", [(y - 0.2, CEIL_Z), (y + 0.12, CEIL_Z), (y + 0.06, CEIL_Z - 0.12),
                     (y - 0.2, CEIL_Z - 0.09)], "x", -0.66, 0.66, "paint_dark", 0.008, 2)
    m = frame_matrix((0, y - 0.07, CEIL_Z - 0.106), (-95, 0, 0))
    for side in (-1, 1):
        greeble(f"header_{side}", m @ Matrix.Translation((side * 0.32, 0, 0)), 0.6, 0.14, rnd)
    for side in (-1, 1):
        box(f"header_light_{side}", (0.03, 0.012, 0.08), (side * 0.03, y + 0.09, CEIL_Z - 0.06),
            (-60, 0, 0), material="led_amber", bev=0.003)


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
