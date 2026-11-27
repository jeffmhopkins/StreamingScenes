"""Procedural spaceship builder (round 2: silhouette-first, plain materials).
Run:
  /workspace/tools/blender/blender -b -P /workspace/3d-output/build_ship.py -- [--compare] [--previews] [--samples N] [--suffix _r2]
  --compare  : render the source-matched camera (1024x576) and write compare_<suffix>.png (source | render | overlay)
  --previews : render preview_front34/side/rear34<suffix>.png
Always exports spaceship.glb + spaceship.blend.
Axes: +X = nose, +Z = up, +Y = port side (the side visible in source.jpg).
"""
import bpy, bmesh, math, random, sys, os
from mathutils import Vector, Matrix

OUT = "/workspace/3d-output"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(name, default):
    return type(default)(argv[argv.index(name) + 1]) if name in argv else default
SAMPLES = arg("--samples", 64); SUFFIX = arg("--suffix", "_r2")
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ----------------------------------------------------------------- materials (plain, shape-first)
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
M = {
    "hull": bsdf_mat("HullGrey", (0.16, 0.16, 0.17), 0.5, 0.5),
    "hull_dark": bsdf_mat("HullGreyDark", (0.09, 0.09, 0.1), 0.5, 0.5),
    "trim": bsdf_mat("TrimDark", (0.035, 0.035, 0.04), 0.7, 0.45),
    "gun": bsdf_mat("GunMetal", (0.05, 0.05, 0.055), 0.9, 0.3),
    "glow": bsdf_mat("AmberLight", (1.0, 0.55, 0.15), 0, 0.4, emit=(1.0, 0.55, 0.15), emit_strength=6),
    "engine": bsdf_mat("EngineGlow", (1.0, 0.45, 0.1), 0, 0.4, emit=(1.0, 0.45, 0.1), emit_strength=15),
    "glass": bsdf_mat("CanopyGlass", (0.03, 0.05, 0.06), 0.0, 0.05, alpha=0.25),
    "interior": bsdf_mat("CabinInterior", (0.05, 0.05, 0.055), 0.3, 0.6),
    "cabinlight": bsdf_mat("CabinLight", (0.9, 0.85, 0.7), 0, 0.5, emit=(1.0, 0.8, 0.55), emit_strength=8),
    "screen": bsdf_mat("Screen", (0.1, 0.25, 0.4), 0, 0.3, emit=(0.25, 0.5, 0.8), emit_strength=1.2),
}

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

def finish(bm, name, mat, bevel=0.0, smooth_angle=35, parent=ROOT, uv_scale=0.16, coll=None, extra_mats=(), recalc=True):
    if recalc: bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
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


def prism(name, pts, vec, mat, **kw):
    """Closed solid: polygon pts (3D) extruded by vec."""
    bm = bmesh.new()
    a = [bm.verts.new(p) for p in pts]; b = [bm.verts.new(Vector(p) + Vector(vec)) for p in pts]
    n = len(a)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(a); bm.faces.new(list(reversed(b)))
    bm.normal_update()
    if bm.calc_volume(signed=True) < 0: bmesh.ops.reverse_faces(bm, faces=bm.faces)
    return finish(bm, name, mat, recalc=False, **kw)

def side_prism(name, poly_xz, y0, y1, mat, **kw):
    """polygon in the XZ (side) plane extruded across Y from y0 to y1."""
    return prism(name, [(x, y0, z) for x, z in poly_xz], (0, y1 - y0, 0), mat, **kw)

def boolean(ob, cutter, op="DIFFERENCE"):
    md = ob.modifiers.new("Bool_" + cutter.name, "BOOLEAN"); md.object = cutter; md.operation = op; md.solver = "EXACT"; md.use_self = True

def lerp(a, b, t): return a + (b - a) * t

# Dimensions below were back-projected from source.jpg through the matching camera (tools/camfit.py):
# nose front X~5.9, wing-pod tips X~-7.55, belly Z~-1.25, roof Z~2.0, turret top Z~2.45 (camera yaw 40, pitch 8).

# =================================================================== LOWER HULL (central body)
# deck line (top of lower hull, where the cabin sits): (x, z)
DECK = [(5.86, -0.22), (5.12, 0.18), (4.9, 0.24), (2.3, 0.36), (0.0, 0.32), (-3.5, 0.30), (-5.6, 0.15)]
deck = lambda x: interp(DECK, x, 1)
# (x, halfwidth, z_bottom)
HULL = [(5.86, 0.95, -0.80), (5.62, 1.02, -0.92), (4.7, 1.12, -1.08), (3.6, 1.25, -1.2), (1.0, 1.28, -1.25),
        (-1.0, 1.25, -1.15), (-3.0, 1.18, -1.0), (-4.6, 1.05, -0.85), (-5.6, 0.85, -0.62)]
def hull_ring(x, hw, zb):
    zd = deck(x); h = zd - zb
    pts = [(0.5, zb), (0.88, zb + h * 0.15), (1.0, zb + h * 0.38), (1.0, zd - h * 0.14), (0.9, zd)]
    return [(x, hw * py, pz) for py, pz in pts] + [(x, -hw * py, pz) for py, pz in reversed(pts)]
loft("Hull_Core", [hull_ring(*s) for s in HULL], M["hull"], bevel=0.015)
hw_at = lambda x: interp(HULL, x, 1); zb_at = lambda x: interp(HULL, x, 2)

# ---- side sponsons ("cheeks"): bulging lower armour from behind the nose back to the wing pods
# (x, inner_y, outer_y, z_bottom, z_top)
SPON = [(5.38, 0.95, 1.22, -0.72, -0.30), (5.05, 0.95, 1.62, -0.96, -0.05), (3.2, 0.95, 1.74, -1.15, 0.15),
        (0.6, 0.95, 1.76, -1.15, 0.22), (-1.8, 0.95, 1.72, -1.02, 0.25), (-3.8, 0.95, 1.56, -0.86, 0.25), (-5.3, 0.95, 1.25, -0.6, 0.12)]
def spon_ring(x, yi, yo, zb, zt, sy):
    h = zt - zb; w = yo - yi
    pts = [(yi, zb + h * 0.1), (yi + w * 0.5, zb), (yo - w * 0.12, zb + h * 0.2), (yo, zb + h * 0.42),
           (yo, zb + h * 0.62), (yo - w * 0.25, zt), (yi, zt)]
    return [(x, sy * py, pz) for py, pz in pts]
for sy in (1, -1):
    loft(f"Sponson_{sy}", [spon_ring(*s, sy) for s in SPON], M["hull"], bevel=0.015)
    belt = [[(x, sy * (yo + 0.05), zb + (zt - zb) * f) for f in (0.40, 0.64)] + [(x, sy * (yo - 0.1), zb + (zt - zb) * f) for f in (0.64, 0.40)]
            for (x, yi, yo, zb, zt) in SPON[1:-1]]
    loft(f"SponsonBelt_{sy}", belt, M["hull_dark"], bevel=0.008)
    # upper sponson armour plate (layering between cheek and cabin wall)
    loft(f"SponsonTopPlate_{sy}", [[(x, sy * yi2, deck(x) - 0.02), (x, sy * (yo - 0.12), zt + 0.05), (x, sy * (yo - 0.2), zt - 0.03), (x, sy * yi2, deck(x) - 0.12)]
                                   for x, yi2, yo, zt in [(4.9, 1.05, 1.62, -0.03), (3.2, 1.18, 1.74, 0.17), (0.6, 1.22, 1.76, 0.24), (-1.8, 1.2, 1.72, 0.27)]],
         M["hull_dark"], bevel=0.008)

# =================================================================== NOSE
# blunt front face at X~6.0 (Z -1.0..-0.3), layered sloping plates on the nose deck, chin below
def deck_plate(name, x0, x1, w0, w1, t, mat, lift=0.0):
    pts = [(x0, w0, deck(x0) + lift), (x1, w1, deck(x1) + lift), (x1, -w1, deck(x1) + lift), (x0, -w0, deck(x0) + lift)]
    prism(name, pts, (0, 0, t), mat, bevel=0.01)
deck_plate("NosePlate_1", 4.95, 5.92, 1.05, 0.84, 0.07, M["hull"], lift=-0.03)
deck_plate("NosePlate_2", 5.1, 5.78, 0.8, 0.62, 0.06, M["hull_dark"], lift=0.03)
deck_plate("NosePlate_3", 5.25, 5.62, 0.5, 0.4, 0.05, M["hull"], lift=0.08)
# nose front frame + lights
box("NoseFrontFrame", (5.87, 0, -0.5), (0.06, 1.55, 0.5), M["hull_dark"], bevel=0.01)
box("NoseLight_A", (5.91, 0, -0.36), (0.03, 0.75, 0.06), M["glow"])
box("NoseLight_B", (5.91, 0, -0.56), (0.03, 0.45, 0.05), M["glow"])
for sy in (1, -1):
    # forward corner blocks flanking the nose face, each with a vertical lamp
    box(f"NoseCornerBlock_{sy}", (5.9, sy * 0.98, -0.47), (0.3, 0.24, 0.6), M["hull"], bevel=0.015, taper=(0.7, 0.8))
    box(f"NoseCornerLamp_{sy}", (6.06, sy * 0.98, -0.5), (0.03, 0.07, 0.22), M["glow"])
    box(f"NoseSideLamp_{sy}", (5.91, sy * 0.68, -0.46), (0.03, 0.05, 0.16), M["glow"])
    box(f"CheekLight_{sy}", (5.3, sy * 1.25, -0.52), (0.03, 0.34, 0.06), M["glow"], rot=(0, 0, sy * -1.0))
    box(f"CheekLamp_{sy}", (5.1, sy * 1.63, -0.42), (0.14, 0.03, 0.05), M["glow"])
loft("Chin", [[(x, sy * w, z) for sy, w, z in [(1, w0, zt), (1, w0 * 0.8, zb), (-1, w0 * 0.8, zb), (-1, w0, zt)]]
              for x, w0, zt, zb in [(5.86, 0.75, -0.74, -0.86), (5.2, 0.85, -0.92, -1.12), (4.6, 0.9, -1.05, -1.22)]], M["hull_dark"], bevel=0.01)
for sy in (1, -1):
    cyl(f"CannonShroud_{sy}", (5.95, sy * 0.2, -0.72), 0.08, 0.5, M["gun"], verts=10)
    cyl(f"CannonBarrel_{sy}", (6.45, sy * 0.2, -0.72), 0.035, 0.8, M["gun"], verts=10)
    cyl(f"CannonMuzzle_{sy}", (6.85, sy * 0.2, -0.72), 0.05, 0.08, M["gun"], verts=10)

# =================================================================== SUPERSTRUCTURE / CANOPY
# (x, halfwidth_bottom, z_top, top_width_factor) ; bottom follows the deck line
SUP = [(5.2, 1.04, 0.22, 0.82), (3.55, 1.18, 1.40, 0.74), (2.7, 1.22, 1.6, 0.72), (1.9, 1.25, 1.74, 0.71), (1.0, 1.27, 1.85, 0.7),
       (0.2, 1.28, 1.92, 0.7), (-1.0, 1.28, 1.97, 0.7), (-3.5, 1.24, 2.02, 0.7), (-4.5, 1.15, 1.95, 0.68), (-5.1, 1.0, 1.6, 0.66)]
BAND = 0.16   # sloped roof-edge band above the windows
def sup_ring(x, hw, zt, tf, inset=0.0):
    zb = deck(x) - 0.04
    k = min(1.0, (zt - zb) / 0.6)
    pts = [(1.0, zb), (1.0, zb + 0.1 * k), (tf + 0.1, zt - BAND * k), (tf, zt)]
    return [(x, (hw - inset) * py, pz - (inset if pz > zb + 0.01 else 0)) for py, pz in pts] + \
           [(x, -(hw - inset) * py, pz - (inset if pz > zb + 0.01 else 0)) for py, pz in reversed(pts)]
shell = loft("Cabin_Shell", [sup_ring(*s) for s in SUP], M["hull"], cap=True)
zt_sup = lambda x: interp(SUP, x, 2)
def sup_at(x): return (x, interp(SUP, x, 1), interp(SUP, x, 2), interp(SUP, x, 3))
# hollow it with an inset cavity (more robust than solidify at the thin windshield tip)
cav_rings = []
for x in [4.85] + [s_[0] for s_ in SUP[1:-1]] + [SUP[-1][0] + 0.12]:
    r = sup_ring(*sup_at(x), inset=0.09); zb0 = deck(x) - 0.04
    cav_rings.append([(px, py, pz + 0.06 if abs(pz - zb0) < 1e-6 else pz) for px, py, pz in r])
cavity = loft("cut_cavity", cav_rings, None, cap=True, parent=None)

# --- window outlines in the side (XZ) plane, traced from source.jpg via back-projection
_wt = lambda x: zt_sup(x) - BAND - 0.03
SIDE_WIN = [(2.30, deck(2.3) + 0.16), (2.22, _wt(2.22)), (3.45, _wt(3.45)), (4.3, _wt(4.3) - 0.02), (4.80, deck(4.8) + 0.15)]  # rear, top, A-pillar edge, sill
BAY = [(1.60, 0.46), (1.25, 1.50), (1.00, 1.66), (-1.30, 1.66), (-1.85, 1.12), (-1.75, 0.42)]
cutters = [cavity]
for sy in (1, -1):
    cutters.append(side_prism(f"cut_side_{sy}", SIDE_WIN, sy * 0.45, sy * 2.5, None, parent=None))
    cutters.append(side_prism(f"cut_bay_{sy}", BAY, sy * 0.45, sy * 2.5, None, parent=None))
A, B = SUP[0], SUP[1]  # windshield = sloped top face between ring B (top, X=3.0) and ring A (bottom, X=4.48)
def on_slope(u, v):
    x = lerp(B[0], A[0], u); w = lerp(B[1] * B[3], A[1] * A[3], u); z = lerp(B[2], A[2], u)
    return Vector((x, v * w, z))
nrm = (on_slope(1, 1) - on_slope(0, 1)).cross(on_slope(0, -1) - on_slope(0, 1)).normalized()
if nrm.z < 0: nrm = -nrm
WS = [(0.05, 0.9), (0.05, -0.9), (0.95, -0.86), (0.95, 0.86)]   # big trapezoid windshield, thin frame
cutters.append(prism("cut_windshield", [on_slope(u, v) - nrm * 0.25 for u, v in WS], nrm * 0.5, None, parent=None))
def plane_frame(name, inner, outer, n, t0, t1, mat):
    bm = bmesh.new()
    L = len(inner)
    ib = [bm.verts.new(p + n * t0) for p in inner]; ob = [bm.verts.new(p + n * t0) for p in outer]
    it = [bm.verts.new(p + n * t1) for p in inner]; ot = [bm.verts.new(p + n * t1) for p in outer]
    for i in range(L):
        j = (i + 1) % L
        bm.faces.new((it[i], it[j], ot[j], ot[i])); bm.faces.new((ib[j], ib[i], ob[i], ob[j]))
        bm.faces.new((ot[i], ot[j], ob[j], ob[i])); bm.faces.new((ib[i], ib[j], it[j], it[i]))
    return finish(bm, name, mat, recalc=True)
WS_OUT = [(0.0, 0.97), (0.0, -0.97), (1.0, -0.93), (1.0, 0.93)]
plane_frame("WindshieldFrame", [on_slope(u, v) for u, v in WS], [on_slope(u, v) for u, v in WS_OUT], nrm, -0.01, 0.05, M["trim"])
for c in cutters: c.hide_render = True
if "--nobool" not in argv:
    for c in cutters: boolean(shell, c)
for c in cutters:
    if "bay" in c.name or "cavity" in c.name or "--noglass" in argv: continue
    g = loft("Glass_" + c.name[4:], [sup_ring(*s, inset=0.05) for s in SUP], M["glass"], cap=True, smooth_angle=15)
    gs = g.modifiers.new("Solid", "SOLIDIFY"); gs.thickness = 0.012; gs.offset = 0
    boolean(g, c, "INTERSECT")

# window frame trims: strips that sit on the (tumblehome) side wall along each window edge
def wall_y(x, z):
    hw = interp(SUP, x, 1); tf = interp(SUP, x, 3); zt = interp(SUP, x, 2); zb = deck(x) - 0.04
    t = (z - zb - 0.1) / max(zt - BAND - zb - 0.1, 1e-3); t = min(max(t, 0), 1)
    return hw * lerp(1.0, tf + 0.1, t), math.atan2(hw * (1.0 - tf - 0.1), zt - BAND - zb - 0.1)
def frame_ring(name, poly, sy, width=0.06, depth=0.05, closed=True, mat=None):
    n = len(poly) if closed else len(poly) - 1
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(x1 - x0, z1 - z0); ang = math.atan2(z1 - z0, x1 - x0)
        xm, zm = (x0 + x1) / 2, (z0 + z1) / 2
        y, tilt = wall_y(xm, zm)
        box(f"{name}_{i}_{sy}", (xm, sy * (y + 0.01), zm), (L + width, depth, width), mat or M["trim"], rot=(sy * tilt, -ang, 0))
for sy in (1, -1):
    frame_ring("FrameSide", SIDE_WIN, sy)
    frame_ring("FrameBay", BAY, sy, width=0.12, depth=0.07)
    # armour plates on the cabin wall: B-pillar block, and panels behind the bay
    frame_ring("BPillar", [(2.15, 0.55), (1.75, 0.55), (1.45, 1.5), (2.12, 1.55)], sy, width=0.2, depth=0.04, mat=M["hull_dark"])
    frame_ring("AftPanel", [(-2.1, 0.5), (-4.2, 0.5), (-4.2, 1.7), (-2.1, 1.7)], sy, width=0.14, depth=0.04, mat=M["hull_dark"])

# =================================================================== SIMPLE CABIN (low detail by design)
def build_cabin():
    box("Cabin_Floor", (1.4, 0, 0.36), (7.0, 2.2, 0.04), M["interior"])
    box("Cabin_RearWall", (-2.1, 0, 1.1), (0.06, 2.2, 1.5), M["interior"])
    box("Cabin_Divider", (1.95, 0, 1.05), (0.06, 2.2, 1.4), M["interior"])
    box("Cabin_Spine", (-0.1, 0, 0.8), (2.8, 0.3, 0.85), M["interior"])
    for sy in (1, -1):
        for i, x in enumerate((-1.0, -0.1, 0.8)):
            box(f"Screen_{sy}_{i}", (x, sy * 0.16, 1.12), (0.7, 0.01, 0.4), M["screen"])
        box(f"Seat_{sy}", (3.0, sy * 0.45, 0.55), (0.45, 0.42, 0.35), M["interior"])
        box(f"SeatBack_{sy}", (2.75, sy * 0.45, 0.85), (0.08, 0.42, 0.6), M["interior"])
        box(f"CockpitScreen_{sy}", (3.1, sy * 0.85, 0.95), (0.55, 0.01, 0.32), M["screen"])
    box("Cockpit_Console", (4.15, 0, 0.45), (0.8, 1.5, 0.3), M["interior"], taper=(0.6, 1))
    box("Cabin_CeilingLight", (-0.1, 0, 1.8), (2.8, 0.12, 0.02), M["cabinlight"])
    box("Cockpit_CeilingLight", (2.8, 0, 1.55), (0.8, 0.08, 0.02), M["cabinlight"])
if "--nocabin" not in argv: build_cabin()

# =================================================================== TOP: roof plates + turret
def roof_plate(name, x0, x1, w, t=0.06, mat=None):
    pts = [(x0, w, zt_sup(x0)), (x1, w, zt_sup(x1)), (x1, -w, zt_sup(x1)), (x0, -w, zt_sup(x0))]
    prism(name, pts, (0, 0, t), mat or M["hull"], bevel=0.01)
roof_plate("RoofPlate_0", 3.4, 1.5, 0.72); roof_plate("RoofPlate_1", 1.3, -0.2, 0.74)
roof_plate("RoofPlate_2", -2.2, -4.3, 0.72); roof_plate("RoofSpine", 3.2, -4.3, 0.25, 0.1, M["hull_dark"])
TX = -1.15; TZ = zt_sup(TX) + 0.1
cyl("Turret_Base", (TX, 0, TZ + 0.04), 0.42, 0.12, M["hull_dark"], axis="Z", verts=20)
box("Turret_Head", (TX, 0, TZ + 0.24), (1.3, 0.7, 0.36), M["hull"], bevel=0.02, taper=(0.85, 0.85))
box("Turret_Mantlet", (TX + 0.7, 0, TZ + 0.24), (0.16, 0.42, 0.22), M["hull_dark"], bevel=0.01)
box("Turret_Lamp", (TX + 0.2, 0.35, TZ + 0.26), (0.16, 0.01, 0.04), M["glow"])
for sy in (1, -1):
    cyl(f"Turret_Barrel_{sy}", (TX + 1.1, sy * 0.1, TZ + 0.24), 0.03, 0.7, M["gun"], verts=10)
    cyl(f"Turret_BarrelCollar_{sy}", (TX + 0.88, sy * 0.1, TZ + 0.24), 0.05, 0.2, M["gun"], verts=10)
    cyl(f"Turret_Muzzle_{sy}", (TX + 1.45, sy * 0.1, TZ + 0.24), 0.05, 0.08, M["gun"], verts=10)

# =================================================================== REAR: twin upper engine nacelles (segmented, tapered)
NZ = 1.22
for sy in (1, -1):
    yc = sy * 0.5
    loft(f"TopNacelle_{sy}", [[(x, yc + r * math.cos(a), NZ + r * math.sin(a)) for a in [k * math.pi / 6 for k in range(12)]]
                              for x, r in [(-4.6, 0.2), (-5.1, 0.3), (-6.4, 0.3), (-6.85, 0.26), (-7.0, 0.21)]], M["hull"], bevel=0.01)
    for i, x in enumerate((-5.6, -6.05, -6.5)):
        cyl(f"NacelleRing_{i}_{sy}", (x, yc, NZ), 0.33, 0.1, M["hull_dark"], verts=12)
    cyl(f"TopNacelleGlow_{sy}", (-7.01, yc, NZ), 0.17, 0.02, M["engine"], verts=16)
    box(f"NacelleLamp_{sy}", (-5.8, yc + sy * 0.32, NZ), (0.25, 0.02, 0.04), M["glow"])

# =================================================================== REAR: wing pods sweeping back (layered armour)
# (x, y_center, half_width, z_bottom, z_top)
POD = [(-1.35, 1.65, 0.2, 0.3, 0.62), (-2.0, 1.74, 0.45, -0.15, 1.1), (-2.6, 1.8, 0.52, -0.38, 1.26), (-4.4, 1.97, 0.55, -0.4, 1.15),
       (-5.35, 2.07, 0.53, -0.3, 0.95), (-5.7, 2.12, 0.48, -0.26, 0.68), (-7.35, 2.32, 0.46, -0.22, 0.56), (-7.55, 2.34, 0.42, -0.18, 0.46)]
for sy in (1, -1):
    rings = []
    for x, yc, hw, zb, zt in POD:
        h = zt - zb
        pts = [(-0.8, zb), (0.55, zb), (1.0, zb + h * 0.3), (1.0, zb + h * 0.62), (0.7, zt), (-0.75, zt), (-1.0, zb + h * 0.6), (-1.0, zb + h * 0.2)]
        rings.append([(x, sy * (yc + hw * py), pz) for py, pz in pts])
    loft(f"WingPod_{sy}", rings, M["hull"], bevel=0.015)
    # layered plates on the pod: upper shoulder plate and side belt
    loft(f"WingPodPlate_{sy}", [[(x, sy * (yc + hw * py), zt + dz) for py, dz in [(-0.6, 0.0), (0.72, -0.02), (0.68, 0.06), (-0.55, 0.07)]]
                                for x, yc, hw, zb, zt in POD[1:5]], M["hull_dark"], bevel=0.008)
    # tip slab top plate
    loft(f"WingTipPlate_{sy}", [[(x, sy * (yc + hw * py), zt + dz) for py, dz in [(-0.8, 0.0), (0.85, -0.02), (0.8, 0.05), (-0.75, 0.06)]]
                                for x, yc, hw, zb, zt in POD[5:7]], M["hull_dark"], bevel=0.008)
    loft(f"WingPodBelt_{sy}", [[(x, sy * (yc + hw * py), zb + (zt - zb) * f) for py, f in [(1.0, 0.35), (1.06, 0.4), (1.06, 0.58), (1.0, 0.63)]]
                               for x, yc, hw, zb, zt in POD[1:]], M["hull_dark"], bevel=0.006)
    for i, (xa, xb) in enumerate([(-5.4, -6.3), (-6.45, -7.4)]):
        xm = (xa + xb) / 2; yc = interp(POD, xm, 1); hw = interp(POD, xm, 2); zb = interp(POD, xm, 3); zt = interp(POD, xm, 4)
        box(f"PodStrip_{i}_{sy}", (xm, sy * (yc + hw * 1.06 + 0.01), zb + (zt - zb) * 0.49), (xa - xb, 0.03, 0.05), M["glow"], rot=(0, 0, sy * -0.17))
    box(f"PodTipLamp_{sy}", (-7.57, sy * 2.4, 0.15), (0.03, 0.22, 0.04), M["glow"])
    box(f"PodTipLamp2_{sy}", (-7.57, sy * 2.4, 0.0), (0.03, 0.22, 0.04), M["glow"])
    box(f"PodSign_{sy}", (-2.9, sy * 2.25, 0.4), (0.5, 0.02, 0.2), M["trim"])
    box(f"PodShoulderLamp_{sy}", (-2.75, sy * 2.2, 1.0), (0.2, 0.02, 0.05), M["glow"])
    # ventral thruster with glowing intake ring
    cyl(f"VentralPod_{sy}", (-4.55, sy * 1.4, -0.87), 0.24, 1.6, M["hull_dark"], verts=14)
    cyl(f"VentralPodRing_{sy}", (-3.75, sy * 1.4, -0.87), 0.27, 0.1, M["trim"], verts=14)
    cyl(f"VentralPodGlow_{sy}", (-3.69, sy * 1.4, -0.87), 0.19, 0.02, M["engine"], verts=14)
    # hull / sponson light strips
    for i, (x, f, L) in enumerate([(3.6, 0.52, 0.7), (1.4, 0.52, 0.9), (-0.7, 0.52, 0.7), (2.5, 0.15, 0.5), (-1.4, 0.15, 0.6)]):
        yo = interp(SPON, x, 2); zb = interp(SPON, x, 3); zt = interp(SPON, x, 4)
        box(f"HullStrip_{i}_{sy}", (x, sy * (yo + 0.06), zb + (zt - zb) * f), (L, 0.03, 0.045), M["glow"])
    for i, x in enumerate((4.0, 2.6, 0.9, -2.6)):
        y, _ = wall_y(x, deck(x) + 0.05)
        box(f"ShellLamp_{i}_{sy}", (x, sy * (y + 0.01), deck(x) + 0.08), (0.2, 0.03, 0.04), M["glow"])

# main rear: tapered hull end with recessed exhausts
for sy in (1, -1):
    cyl(f"MainNozzle_{sy}", (-5.63, sy * 0.42, -0.25), 0.22, 0.14, M["trim"], verts=16, r2=0.26, cap=False)
    cyl(f"MainGlow_{sy}", (-5.62, sy * 0.42, -0.25), 0.21, 0.02, M["engine"], verts=16)

# =================================================================== apply modifiers, cleanup, export
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(ROOT.children):
    if ob.type == "MESH" and ob.modifiers:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        old = ob.data; ob.modifiers.clear(); ob.data = me; bpy.data.meshes.remove(old)
for c in cutters: bpy.data.objects.remove(c)
bpy.data.collections.remove(CUTTERS)

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

# =================================================================== rendering
# camera tuned to match source.jpg (nose left, port side, slightly from the front and above)
SRC_CAM = dict(yaw=arg("--yaw", 40.0), pitch=arg("--pitch", 8.0), dist=arg("--dist", 27.0), lens=arg("--lens", 70.0),
               tx=arg("--tx", 0.0), ty=arg("--ty", 0.0), tz=arg("--tz", 0.3), roll=arg("--roll", 0.0))
def setup_render(res, transparent):
    scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = transparent
    scene.view_settings.view_transform = "AgX"; scene.view_settings.look = "AgX - Medium High Contrast"
    if scene.world: return
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
    light("Key", "AREA", (8, 10, 8), 2500, 6); light("Rim", "AREA", (-10, -6, 5), 2000, 6, (0.7, 0.8, 1.0)); light("Fill", "AREA", (6, -10, 2), 800, 6)

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data); scene.collection.objects.link(cam); scene.camera = cam
def place_cam(yaw, pitch, dist, lens, tx=0, ty=0, tz=0, roll=0):
    cam_data.lens = lens
    t = Vector((tx, ty, tz)); y, p = math.radians(yaw), math.radians(pitch)
    cam.location = t + dist * Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p)))
    q = (t - cam.location).to_track_quat("-Z", "Y")
    cam.rotation_euler = (q @ __import__("mathutils").Quaternion((0, 0, 1), math.radians(roll))).to_euler()
def render(path):
    scene.render.filepath = path; bpy.ops.render.render(write_still=True); print("RENDERED", path)

if "--compare" in argv:
    setup_render((1024, 576), True); place_cam(**SRC_CAM)
    render(os.path.join(OUT, "compare_render.png"))
if "--previews" in argv:
    setup_render((1280, 720), False)
    for name, c in {"preview_front34": SRC_CAM,
                    "preview_side": dict(yaw=0, pitch=4, dist=27, lens=60, tz=0.2, tx=-0.6),
                    "preview_rear34": dict(yaw=-50, pitch=16, dist=27, lens=60, tz=0.2, tx=-0.6)}.items():
        place_cam(**c); render(os.path.join(OUT, name + SUFFIX + ".png"))
