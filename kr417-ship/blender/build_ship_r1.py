"""Procedural spaceship builder.
Run:  /workspace/tools/blender/blender -b -P /workspace/3d-output/build_ship.py -- [--no-render] [--samples N]
Outputs spaceship.glb + preview_*.png in /workspace/3d-output.
Axes: +X = nose (forward), +Z = up, +Y = port (left side seen in source image).
"""
import bpy, bmesh, math, random, sys, os
import numpy as np
from mathutils import Vector, Matrix

OUT = "/workspace/3d-output"
TEX = os.path.join(OUT, "textures")
os.makedirs(TEX, exist_ok=True)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
DO_RENDER = "--no-render" not in argv
SAMPLES = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 96
RES = (1280, 720)
random.seed(7)
rng = np.random.default_rng(7)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ----------------------------------------------------------------- textures
def save_img(name, arr):
    arr = np.clip(arr, 0, 1)
    h, w = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, -1)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.ones((h, w, 1))], -1)
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.pixels.foreach_set(arr[::-1].astype(np.float32).ravel())
    img.filepath_raw = os.path.join(TEX, name + ".png")
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img

def blur(a, k=2):
    for _ in range(k):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
    return a

def make_panel_textures(S=1024):
    height = np.ones((S, S)) * 0.5
    tone = np.zeros((S, S))
    rough = np.ones((S, S)) * 0.5
    rects = [(0, 0, S, S)]
    out = []
    while rects:  # recursive panel splits (tileable: all splits inside the square)
        x, y, w, h = rects.pop()
        if (w > 90 or h > 90) and (w * h > 9000) and random.random() < 0.93:
            if w > h:
                c = int(w * random.uniform(0.3, 0.7)); rects += [(x, y, c, h), (x + c, y, w - c, h)]
            else:
                c = int(h * random.uniform(0.3, 0.7)); rects += [(x, y, w, c), (x, y + c, w, h - c)]
        else:
            out.append((x, y, w, h))
    for x, y, w, h in out:
        tone[y:y + h, x:x + w] = rng.normal(0, 0.05)
        rough[y:y + h, x:x + w] = 0.45 + rng.uniform(-0.1, 0.12)
        g = 2
        height[y:y + g, x:x + w] = 0.0; height[y:y + h, x:x + g] = 0.0
        if random.random() < 0.35 and w > 40 and h > 40:  # rivets
            for (px, py) in [(x + 8, y + 8), (x + w - 9, y + 8), (x + 8, y + h - 9), (x + w - 9, y + h - 9)]:
                height[py - 1:py + 2, px - 1:px + 2] = 0.8
        if random.random() < 0.15 and w > 60 and h > 30:  # vent slats
            for i in range(y + 10, y + h - 10, 6):
                height[i:i + 2, x + 12:x + w - 12] = 0.15
    noise = blur(rng.normal(0, 1, (S, S)), 1) * 0.03
    grime = blur(rng.normal(0, 1, (S // 8, S // 8)), 2)
    grime = np.kron(grime, np.ones((8, 8)))
    grime = blur(grime, 6); grime = (grime - grime.min()) / (np.ptp(grime) + 1e-6)
    groove = blur((height < 0.05).astype(float), 2)
    base = 0.24 + tone + noise - groove * 0.06 - grime * 0.04
    base = np.clip(base, 0.02, 1)
    albedo = np.stack([base * 0.95, base * 0.98, base * 1.05], -1)
    edge = blur((height < 0.05).astype(float), 1)
    albedo += (edge - groove).clip(0, 1)[..., None] * 0.04  # slight edge wear
    # normal from height
    hb = blur(height, 1)
    dx = (np.roll(hb, -1, 1) - np.roll(hb, 1, 1)) * 3.0
    dy = (np.roll(hb, -1, 0) - np.roll(hb, 1, 0)) * 3.0
    n = np.stack([-dx, dy, np.ones_like(dx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    normal = n * 0.5 + 0.5
    rough = blur(rough, 1) + grime * 0.15 + groove * 0.2
    orm = np.stack([1 - groove * 0.5, np.clip(rough, 0, 1), np.ones((S, S)) * 0.85], -1)
    return save_img("hull_albedo", albedo), save_img("hull_normal", normal), save_img("hull_orm", orm)

def make_screen_texture():
    W, H = 256, 160
    a = np.zeros((H, W, 3)) + np.array([0.02, 0.05, 0.08])
    cols = [(0.9, 0.2, 0.2), (0.95, 0.6, 0.1), (0.9, 0.9, 0.2), (0.2, 0.85, 0.3), (0.2, 0.7, 0.95), (0.45, 0.3, 0.9), (0.9, 0.3, 0.7)]
    for i, c in enumerate(cols):
        a[95:130, 20 + i * 31:20 + i * 31 + 29] = c
    a[25:35, 30:150] = (0.8, 0.9, 1.0); a[45:52, 30:200] = (0.4, 0.6, 0.8); a[60:66, 30:120] = (0.4, 0.6, 0.8)
    a[:4], a[-4:], a[:, :4], a[:, -4:] = (0.3, 0.5, 0.7), (0.3, 0.5, 0.7), (0.3, 0.5, 0.7), (0.3, 0.5, 0.7)
    return save_img("screen", a)

# ----------------------------------------------------------------- materials
def bsdf_mat(name, color=(0.1, 0.1, 0.1), metal=0.0, rough=0.5, emit=None, emit_strength=0.0, alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = emit_strength
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        m.blend_method = "BLEND"
        try: m.surface_render_method = "BLENDED"
        except Exception: pass
    return m

def textured_mat(name, albedo, normal, orm, tint=(1, 1, 1), nstrength=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    ta = nt.nodes.new("ShaderNodeTexImage"); ta.image = albedo
    if tint != (1, 1, 1):
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(ta.outputs["Color"], mix.inputs[6]); mix.inputs[7].default_value = (*tint, 1)
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    else:
        nt.links.new(ta.outputs["Color"], b.inputs["Base Color"])
    to = nt.nodes.new("ShaderNodeTexImage"); to.image = orm; to.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(to.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = normal; tn.image.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nstrength
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m

alb, nrm, orm = make_panel_textures()
M = {
    "hull": textured_mat("HullMetal", alb, nrm, orm),
    "hull_dark": textured_mat("HullMetalDark", alb, nrm, orm, tint=(0.55, 0.55, 0.6)),
    "trim": bsdf_mat("TrimDark", (0.025, 0.025, 0.03), 0.8, 0.45),
    "gun": bsdf_mat("GunMetal", (0.05, 0.05, 0.055), 0.9, 0.3),
    "glow": bsdf_mat("AmberLight", (1.0, 0.55, 0.15), 0, 0.4, emit=(1.0, 0.55, 0.15), emit_strength=6),
    "engine": bsdf_mat("EngineGlow", (1.0, 0.45, 0.1), 0, 0.4, emit=(1.0, 0.45, 0.1), emit_strength=18),
    "glass": bsdf_mat("CanopyGlass", (0.03, 0.05, 0.06), 0.0, 0.05, alpha=0.2),
    "interior": bsdf_mat("CabinInterior", (0.06, 0.06, 0.065), 0.3, 0.6),
    "cabinlight": bsdf_mat("CabinLight", (0.9, 0.85, 0.7), 0, 0.5, emit=(1.0, 0.8, 0.55), emit_strength=10),
    "bluelight": bsdf_mat("BlueIndicator", (0.3, 0.6, 1.0), 0, 0.5, emit=(0.3, 0.6, 1.0), emit_strength=4),
}
scr = make_screen_texture()
sm = bpy.data.materials.new("Screen"); sm.use_nodes = True
b = sm.node_tree.nodes["Principled BSDF"]; t = sm.node_tree.nodes.new("ShaderNodeTexImage"); t.image = scr
sm.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"]); sm.node_tree.links.new(t.outputs["Color"], b.inputs["Emission Color"])
b.inputs["Emission Strength"].default_value = 5; b.inputs["Roughness"].default_value = 0.3
M["screen"] = sm

# ----------------------------------------------------------------- mesh helpers
ROOT = bpy.data.objects.new("Spaceship", None); scene.collection.objects.link(ROOT)
CUTTERS = bpy.data.collections.new("Cutters"); scene.collection.children.link(CUTTERS)

def box_uv(bm, scale=0.45):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal; ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            u, v = [(co.y, co.z), (co.x, co.z), (co.x, co.y)][ax]
            l[uv].uv = (u * scale, v * scale)

def finish(bm, name, mat, bevel=0.0, smooth_angle=35, parent=ROOT, uv_scale=0.16, coll=None, extra_mats=()):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    box_uv(bm, uv_scale)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    (coll or scene.collection).objects.link(ob)
    if mat: me.materials.append(mat)
    for em in extra_mats: me.materials.append(em)
    for p in me.polygons: p.use_smooth = True
    me.validate()
    # sharp edges by angle
    bm2 = bmesh.new(); bm2.from_mesh(me)
    for e in bm2.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(smooth_angle):
            e.smooth = False
    bm2.to_mesh(me); bm2.free()
    if bevel > 0:
        md = ob.modifiers.new("Bevel", "BEVEL"); md.width = bevel; md.segments = 2
        md.limit_method = "ANGLE"; md.angle_limit = math.radians(30); md.harden_normals = False
    if parent: ob.parent = parent
    return ob

def loft(name, sections, mat, cap=True, bevel=0.0, **kw):
    """sections: list of rings, each ring a list of (x,y,z) with same count."""
    bm = bmesh.new()
    rings = [[bm.verts.new(p) for p in r] for r in sections]
    n = len(rings[0])
    for a, b2 in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b2[j], b2[i]))
    if cap:
        bm.faces.new(rings[0]); bm.faces.new(list(reversed(rings[-1])))
    return finish(bm, name, mat, bevel, **kw)

def box(name, c, s, mat, rot=(0, 0, 0), bevel=0.0, taper=None, **kw):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        if taper and v.co.z > 0:  # taper top (x,y factor)
            v.co.x *= taper[0]; v.co.y *= taper[1]
        v.co = Vector((v.co.x * s[0], v.co.y * s[1], v.co.z * s[2]))
    R = (Matrix.Rotation(rot[2], 4, "Z") @ Matrix.Rotation(rot[1], 4, "Y") @ Matrix.Rotation(rot[0], 4, "X"))
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ R, verts=bm.verts)
    return finish(bm, name, mat, bevel, **kw)

def cyl(name, c, r, depth, mat, axis="X", verts=16, r2=None, cap=True, **kw):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    rot = {"X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X"), "Z": Matrix.Identity(4)}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ rot, verts=bm.verts)
    return finish(bm, name, mat, **kw)

def interp(tbl, x, idx):
    xs = [r[0] for r in tbl]
    if x >= xs[0]: return tbl[0][idx]
    if x <= xs[-1]: return tbl[-1][idx]
    for a, b2 in zip(tbl, tbl[1:]):
        if b2[0] <= x <= a[0]:
            t = (x - a[0]) / (b2[0] - a[0]); return a[idx] + (b2[idx] - a[idx]) * t

# ----------------------------------------------------------------- lower hull
# (x, halfwidth, z_bottom, z_top)  nose first
HULL = [(5.35, 0.55, -0.30, 0.00), (5.05, 0.95, -0.50, 0.18), (4.4, 1.22, -0.65, 0.33), (3.0, 1.38, -0.74, 0.40),
        (0.0, 1.45, -0.78, 0.44), (-2.5, 1.42, -0.74, 0.44), (-3.9, 1.30, -0.66, 0.42), (-4.55, 1.18, -0.58, 0.38)]
def hull_ring(x, hw, zb, zt):
    hgt = zt - zb
    pts = [(0.62, zb), (0.92, zb + hgt * 0.22), (1.0, zb + hgt * 0.45), (1.04, zb + hgt * 0.55), (1.0, zb + hgt * 0.68), (0.97, zt - hgt * 0.08), (0.84, zt)]
    ring = [(x, hw * py, pz) for py, pz in pts]
    ring += [(x, -hw * py, pz) for py, pz in reversed(pts)]
    return ring
loft("Hull_Lower", [hull_ring(*s) for s in HULL], M["hull"], bevel=0.025)
hw_at = lambda x: interp(HULL, x, 1); zb_at = lambda x: interp(HULL, x, 2); zt_at = lambda x: interp(HULL, x, 3)

# belly keel plate
loft("Hull_Keel", [[(x, hw_at(x) * 0.55 * sy, zb_at(x) + dz) for sy, dz in [(1, 0.02), (0.8, -0.12), (-0.8, -0.12), (-1, 0.02)]]
                   for x in (4.3, 3.0, 0.0, -3.0, -4.3)], M["hull_dark"], bevel=0.02)

# ----------------------------------------------------------------- upper superstructure (cabin shell)
# (x, halfwidth_bottom, z_top, top_width_factor)
SUP = [(4.55, 0.95, 0.42, 0.55), (3.9, 1.12, 0.78, 0.62), (2.9, 1.24, 1.12, 0.70), (1.6, 1.30, 1.28, 0.74),
       (-0.5, 1.32, 1.32, 0.76), (-2.4, 1.30, 1.30, 0.76), (-3.1, 1.22, 1.18, 0.74)]
ZB_SUP = 0.30
def sup_ring(x, hw, zt, tf):
    pts = [(1.0, ZB_SUP), (1.0, ZB_SUP + 0.25), (tf + 0.12, zt - 0.06), (tf, zt)]
    return [(x, hw * py, pz) for py, pz in pts] + [(x, -hw * py, pz) for py, pz in reversed(pts)]
shell = loft("Cabin_Shell", [sup_ring(*s) for s in SUP], M["hull"], cap=True)
sol = shell.modifiers.new("Solid", "SOLIDIFY"); sol.thickness = 0.07; sol.offset = -1

# window cutters
def cutter(name, c, s, rot=(0, 0, 0)):
    return box(name, c, s, None, rot=rot, parent=None, coll=CUTTERS)
cuts = [
    cutter("cut_windshield", (4.05, 0, 0.95), (1.6, 1.15, 0.85), rot=(0, math.radians(-0), 0)),   # front canopy
    cutter("cut_cockpit_side", (2.45, 0, 0.88), (1.25, 3.0, 0.42)),                                # side canopy panes
    cutter("cut_bay", (-0.55, 0, 0.86), (2.9, 3.0, 0.62)),                                         # big side bay
]
# keep a mullion/roof between windshield and side windows: windshield only cuts front faces above z 0.55
cuts[0].location.z += 0.0
for c in cuts: c.hide_render = True
def apply_boolean(ob, cutter_obj, op="DIFFERENCE"):
    md = ob.modifiers.new("Bool_" + cutter_obj.name, "BOOLEAN"); md.object = cutter_obj; md.operation = op; md.solver = "EXACT"
for c in cuts: apply_boolean(shell, c)
md = shell.modifiers.new("Bevel", "BEVEL"); md.width = 0.012; md.segments = 1; md.limit_method = "ANGLE"

# glass = thin inner shell intersected with the cutters
glass = loft("Canopy_Glass", [sup_ring(x, hw - 0.035, zt - 0.035, tf) for x, hw, zt, tf in SUP], M["glass"], cap=True, smooth_angle=20)
gs = glass.modifiers.new("Solid", "SOLIDIFY"); gs.thickness = 0.012; gs.offset = 0
gu = box("glass_union", (0, 0, 0), (0.01, 0.01, 0.01), None, parent=None, coll=CUTTERS)
# intersect glass with each cutter separately -> make 3 glass objects instead (simpler & robust)
glass_parts = []
for c in cuts:
    g = glass.copy(); g.data = glass.data.copy(); scene.collection.objects.link(g); g.parent = ROOT
    g.name = "Glass_" + c.name[4:]
    apply_boolean(g, c, "INTERSECT"); glass_parts.append(g)
bpy.data.objects.remove(glass); bpy.data.objects.remove(gu)

# window frame trims (mullions) on bay and cockpit
for x in (-1.5, -0.55, 0.4):
    for sy in (1, -1):
        y = interp(SUP, x, 1) * sy * 0.935
        box(f"Mullion_{x}_{sy}", (x, y, 0.86), (0.08, 0.1, 0.68), M["trim"], rot=(sy * 0.22, 0, 0))

# ----------------------------------------------------------------- simple cabin interior
box("Cabin_Floor", (0.5, 0, 0.42), (6.6, 2.3, 0.04), M["interior"], parent=ROOT)
box("Cabin_RearWall", (-2.95, 0, 0.8), (0.05, 2.2, 0.8), M["interior"])
box("Cabin_Divider", (1.25, 0, 0.8), (0.06, 1.2, 0.75), M["interior"])
box("Cabin_Spine", (-0.55, 0, 0.72), (2.4, 0.3, 0.6), M["interior"])  # central console in bay
for sy in (1, -1):
    for i, x in enumerate((-1.45, -0.55, 0.35)):  # screens on spine, facing out both sides
        box(f"Screen_{sy}_{i}", (x, sy * 0.155, 0.86), (0.6, 0.01, 0.34), M["screen"])
    box(f"Seat_{sy}", (2.4, sy * 0.45, 0.6), (0.4, 0.4, 0.35), M["interior"])
    box(f"SeatBack_{sy}", (2.18, sy * 0.45, 0.85), (0.08, 0.4, 0.5), M["interior"])
box("Cockpit_Console", (3.35, 0, 0.58), (0.5, 1.4, 0.28), M["interior"], taper=(0.6, 1))
for sy in (1, -1):
    box(f"CockpitScreen_{sy}", (3.25, sy * 0.35, 0.74), (0.01, 0.45, 0.16), M["screen"], rot=(0, math.radians(-35), 0))
box("Cabin_CeilingLight", (-0.55, 0, 1.2), (2.6, 0.12, 0.02), M["cabinlight"])
box("Cockpit_CeilingLight", (2.3, 0, 1.18), (1.0, 0.08, 0.02), M["cabinlight"])

# ----------------------------------------------------------------- side armor plates + strips
plates = [(4.0, 3.0), (2.85, 1.7), (1.55, 0.3), (0.15, -1.3), (-1.45, -2.9), (-3.05, -4.35)]
for i, (x0, x1) in enumerate(plates):
    xc = (x0 + x1) / 2; L = x0 - x1
    for sy in (1, -1):
        hw = hw_at(xc); zb, zt = zb_at(xc), zt_at(xc); h = zt - zb
        box(f"ArmorPlate_{i}_{sy}", (xc, sy * (hw * 1.04 + 0.02), zb + h * 0.55), (L, 0.08, h * 0.32), M["hull_dark"], bevel=0.02, taper=(0.96, 0.7))
        # amber strip on the lower edge of each plate
        if i % 2 == 0 or i == 5:
            box(f"Strip_{i}_{sy}", (xc + L * 0.1, sy * (hw * 1.02 + 0.045), zb + h * 0.36), (L * 0.45, 0.03, 0.035), M["glow"])
        # small square lights
        box(f"Lamp_{i}_{sy}", (x1 + 0.15, sy * (hw * 1.0 + 0.04), zb + h * 0.82), (0.08, 0.03, 0.05), M["glow"])
    # upper hull ledge strips under shell
for sy in (1, -1):
    for i, (xa, xb) in enumerate([(3.6, 2.6), (0.8, -0.4), (-2.2, -3.0)]):
        xc = (xa + xb) / 2
        box(f"LedgeStrip_{i}_{sy}", (xc, sy * (hw_at(xc) * 0.9), zt_at(xc) - 0.02), (xa - xb, 0.03, 0.03), M["glow"])
    # shell side lower light strips
    for i, xc in enumerate((3.4, -2.75)):
        box(f"ShellLamp_{i}_{sy}", (xc, sy * (interp([(s[0], s[1]) for s in SUP], xc, 1) + 0.005), 0.45), (0.3, 0.03, 0.04), M["glow"])

# ----------------------------------------------------------------- nose: lights + twin cannons
for sy in (1, -1):
    box(f"NoseLight_{sy}", (5.22, sy * 0.45, -0.02), (0.06, 0.4, 0.05), M["glow"], rot=(0, 0, sy * -0.5))
    box(f"NoseLightLow_{sy}", (5.0, sy * 0.85, -0.28), (0.05, 0.3, 0.04), M["glow"], rot=(0, 0, sy * -0.7))
    box(f"CannonHousing_{sy}", (5.0, sy * 0.32, -0.38), (0.7, 0.24, 0.2), M["hull_dark"], bevel=0.02)
    for dz in (0.05, -0.05):
        cyl(f"CannonBarrel_{sy}_{dz}", (5.85, sy * 0.32, -0.38 + dz), 0.03, 1.1, M["gun"], verts=10)
    cyl(f"CannonMuzzle_{sy}", (6.42, sy * 0.32, -0.38), 0.06, 0.06, M["gun"], verts=12)
box("NoseIntake", (5.1, 0, 0.12), (0.4, 0.5, 0.06), M["trim"], rot=(0, -0.4, 0))

# ----------------------------------------------------------------- top turret
TX, TZ = 0.9, 1.31
cyl("Turret_Base", (TX, 0, TZ + 0.05), 0.32, 0.1, M["hull_dark"], axis="Z", verts=20)
cyl("Turret_Ring", (TX, 0, TZ + 0.11), 0.26, 0.04, M["trim"], axis="Z", verts=20)
box("Turret_Head", (TX, 0, TZ + 0.24), (0.5, 0.36, 0.22), M["hull"], bevel=0.02, taper=(0.75, 0.85))
box("Turret_Mantlet", (TX + 0.3, 0, TZ + 0.24), (0.12, 0.3, 0.14), M["hull_dark"])
box("Turret_Lamp", (TX + 0.2, 0, TZ + 0.355), (0.12, 0.08, 0.015), M["glow"])
for sy in (1, -1):
    cyl(f"Turret_Barrel_{sy}", (TX + 0.75, sy * 0.08, TZ + 0.24), 0.025, 0.85, M["gun"], verts=10)
    cyl(f"Turret_Muzzle_{sy}", (TX + 1.17, sy * 0.08, TZ + 0.24), 0.04, 0.06, M["gun"], verts=10)

# roof greebles
for i in range(8):
    x = random.uniform(-2.9, 2.2); y = random.uniform(-0.75, 0.75)
    if abs(x - TX) < 0.45: continue
    z = interp(SUP, x, 2)
    box(f"RoofGreeble_{i}", (x, y, z + 0.025), (random.uniform(0.3, 0.7), random.uniform(0.2, 0.45), 0.035), M["hull"], bevel=0.01)
# hull deck greebles (front deck and rear deck)
for i in range(14):
    x = random.choice([random.uniform(4.0, 4.6), random.uniform(-4.4, -3.2)]); y = random.uniform(-0.8, 0.8)
    box(f"DeckGreeble_{i}", (x, y, zt_at(x) + 0.03), (random.uniform(0.1, 0.4), random.uniform(0.1, 0.35), 0.06), M["hull_dark"])
# rear roof spine block
box("RearSpine", (-3.6, 0, zt_at(-3.6) + 0.18), (1.4, 1.0, 0.36), M["hull"], bevel=0.02, taper=(0.85, 0.75))
for sy in (1, -1):
    box(f"RearSpineLamp_{sy}", (-3.4, sy * 0.47, zt_at(-3.4) + 0.2), (0.4, 0.03, 0.03), M["glow"])

# ----------------------------------------------------------------- side nacelles / wing pods
for sy in (1, -1):
    yc = sy * 2.05
    NAC = [(-0.6, 0.18, 0.18), (-1.3, 0.38, 0.3), (-2.4, 0.46, 0.36), (-3.8, 0.48, 0.38), (-4.8, 0.42, 0.34)]
    rings = []
    for x, hw, hh in NAC:
        pts = [(0.7, -hh), (1, -hh * 0.4), (1, hh * 0.5), (0.75, hh), (-0.75, hh), (-1, hh * 0.5), (-1, -hh * 0.4), (-0.7, -hh)]
        rings.append([(x, yc + hw * py, 0.05 + pz) for py, pz in pts])
    loft(f"Nacelle_{sy}", rings, M["hull"], bevel=0.02)
    # pylon connecting nacelle to hull
    loft(f"Pylon_{sy}", [[(x, sy * yy, zz) for yy, zz in [(1.25, 0.25), (1.7, 0.2), (1.7, -0.05), (1.25, -0.2)]] for x in (-1.6, -3.9)], M["hull_dark"], bevel=0.015)
    # wing-tip extension plate (rear outboard)
    box(f"WingPlate_{sy}", (-3.4, sy * 2.65, 0.08), (2.0, 0.35, 0.08), M["hull_dark"], bevel=0.015, taper=(0.9, 1))
    for i, x in enumerate((-1.9, -3.1, -4.2)):
        box(f"NacStrip_{i}_{sy}", (x, yc + sy * 0.49, -0.05), (0.75, 0.03, 0.035), M["glow"])
    box(f"NacTipLamp_{sy}", (-0.75, yc, 0.05), (0.04, 0.2, 0.05), M["glow"])
    # nacelle exhaust
    cyl(f"NacNozzle_{sy}", (-4.95, yc, 0.05), 0.3, 0.3, M["trim"], verts=20, r2=0.34, cap=False)
    cyl(f"NacGlow_{sy}", (-4.9, yc, 0.05), 0.29, 0.02, M["engine"], verts=20)
    # under-pod thruster (glowing ring seen in source under the hull rear)
    cyl(f"VentralPod_{sy}", (-2.6, sy * 1.05, -0.78), 0.17, 1.4, M["hull_dark"], verts=14)
    cyl(f"VentralPodGlow_{sy}", (-1.89, sy * 1.05, -0.78), 0.12, 0.02, M["engine"], verts=14)
    cyl(f"VentralPodRing_{sy}", (-1.93, sy * 1.05, -0.78), 0.18, 0.06, M["trim"], verts=14)

# ----------------------------------------------------------------- main rear engines
box("EngineBlock", (-4.75, 0, -0.12), (0.5, 1.9, 0.75), M["hull_dark"], bevel=0.02)
for sy in (1, -1):
    cyl(f"MainNozzle_{sy}", (-5.1, sy * 0.48, -0.12), 0.32, 0.4, M["trim"], verts=24, r2=0.38, cap=False)
    cyl(f"MainGlow_{sy}", (-5.05, sy * 0.48, -0.12), 0.31, 0.02, M["engine"], verts=24)
    box(f"RearLamp_{sy}", (-4.6, sy * 1.16, 0.25), (0.25, 0.03, 0.04), M["glow"])

# ----------------------------------------------------------------- apply modifiers, cleanup
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(ROOT.children):
    if ob.type == "MESH" and ob.modifiers:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        old = ob.data; ob.modifiers.clear(); ob.data = me; bpy.data.meshes.remove(old)
for c in list(CUTTERS.objects): bpy.data.objects.remove(c)
bpy.data.collections.remove(CUTTERS)

# join by material -> fewer draw calls (keeps object names readable-ish)
def join_all():
    groups = {}
    for ob in ROOT.children:
        if ob.type == "MESH": groups.setdefault(ob.data.materials[0].name if ob.data.materials else "none", []).append(ob)
    for mname, obs in groups.items():
        bpy.ops.object.select_all(action="DESELECT")
        for o in obs: o.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        bpy.ops.object.join(); obs[0].name = "Ship_" + mname
join_all()

tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in ROOT.children if o.type == "MESH")
print("TRIANGLES", tris)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "spaceship.glb"), export_format="GLB", export_apply=True, export_yup=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "spaceship.blend"))

# ----------------------------------------------------------------- render previews
if DO_RENDER:
    scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
    world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
    nt = world.node_tree; bg = nt.nodes["Background"]; bg.inputs[0].default_value = (0.12, 0.14, 0.17, 1); bg.inputs[1].default_value = 1.2
    bg2 = nt.nodes.new("ShaderNodeBackground"); bg2.inputs[0].default_value = (0.32, 0.34, 0.37, 1)
    lp = nt.nodes.new("ShaderNodeLightPath"); mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0]); nt.links.new(bg.outputs[0], mix.inputs[1]); nt.links.new(bg2.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes["World Output"].inputs[0])
    def light(name, typ, loc, energy, size=5, color=(1, 1, 1)):
        L = bpy.data.lights.new(name, typ); L.energy = energy; L.color = color
        if typ == "AREA": L.size = size
        o = bpy.data.objects.new(name, L); scene.collection.objects.link(o); o.location = loc
        o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 3.0; sun.angle = 0.1
    so = bpy.data.objects.new("Sun", sun); scene.collection.objects.link(so); so.rotation_euler = (math.radians(40), math.radians(10), math.radians(150))
    light("Key", "AREA", (8, 10, 8), 2500, 6)
    light("Rim", "AREA", (-10, -6, 5), 2000, 6, (0.7, 0.8, 1.0))
    light("Fill", "AREA", (6, -10, 2), 800, 6)
    cam_data = bpy.data.cameras.new("Cam"); cam_data.lens = 50
    cam = bpy.data.objects.new("Cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam
    views = {
        "preview_front34": ((10.5, 13.5, 4.2), (0.3, 0.2, 0.1)),   # matches source: nose left, port side visible
        "preview_side": ((0.0, 17.5, 1.6), (0.3, 0, 0.2)),
        "preview_rear34": ((-12.0, -11.5, 5.0), (-0.3, 0, 0.0)),
    }
    for name, (loc, tgt) in views.items():
        cam.location = loc
        cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(OUT, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", scene.render.filepath)
