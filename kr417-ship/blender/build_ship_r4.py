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
SAMPLES = arg("--samples", 64); SUFFIX = arg("--suffix", "_r4")
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
    "hull": bsdf_mat("HullGrey", (0.075, 0.075, 0.08), 0.5, 0.45),
    "hull_dark": bsdf_mat("HullGreyDark", (0.04, 0.04, 0.045), 0.5, 0.5),
    "trim": bsdf_mat("TrimDark", (0.018, 0.018, 0.02), 0.7, 0.45),
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
DECK = [(5.86, -0.22), (5.12, 0.18), (4.9, 0.24), (2.3, 0.36), (0.0, 0.32), (-3.5, 0.30), (-5.6, 0.15), (-6.35, 0.08)]
deck = lambda x: interp(DECK, x, 1)
# (x, halfwidth, z_bottom)
HULL = [(5.86, 0.95, -0.80), (5.62, 1.02, -0.9), (4.7, 1.12, -1.03), (3.6, 1.25, -1.17), (1.8, 1.28, -1.33), (0.6, 1.28, -1.3),
        (-1.0, 1.25, -1.1), (-3.0, 1.18, -1.0), (-4.6, 1.05, -0.85), (-5.6, 0.8, -0.6), (-6.35, 0.45, -0.38)]
def hull_ring(x, hw, zb):
    zd = deck(x); h = zd - zb
    pts = [(0.5, zb), (0.88, zb + h * 0.15), (1.0, zb + h * 0.38), (1.0, zd - h * 0.14), (0.9, zd)]
    return [(x, hw * py, pz) for py, pz in pts] + [(x, -hw * py, pz) for py, pz in reversed(pts)]
loft("Hull_Core", [hull_ring(*s) for s in HULL], M["hull"], bevel=0.015)
hw_at = lambda x: interp(HULL, x, 1); zb_at = lambda x: interp(HULL, x, 2)

# ---- side sponsons ("cheeks"): bulging lower armour from behind the nose back to the wing pods
# (x, inner_y, outer_y, z_bottom, z_top)
SPON = [(5.38, 0.95, 1.22, -0.70, -0.30), (5.05, 0.95, 1.62, -0.9, -0.05), (3.2, 0.95, 1.74, -1.17, 0.15), (1.9, 0.95, 1.76, -1.24, 0.19),
        (0.6, 0.95, 1.76, -1.2, 0.22), (-1.8, 0.95, 1.72, -0.98, 0.25), (-3.8, 0.95, 1.56, -0.86, 0.25), (-5.3, 0.95, 1.25, -0.6, 0.12)]
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
    # segmented armour panels on the sponson upper face (layered plates like the source)
    segs = [(4.95, 3.95), (3.85, 2.7), (2.6, 1.3), (1.2, -0.1), (-0.2, -1.5), (-1.6, -2.9)]
    for k_, (x0, x1) in enumerate(segs):
        rings = []
        for x in (x0, x1):
            _, yi, yo, zb, zt = (x, interp(SPON, x, 1), interp(SPON, x, 2), interp(SPON, x, 3), interp(SPON, x, 4))
            h = zt - zb; w = yo - yi
            o = [(yo, zb + h * 0.66), (yo - w * 0.22, zt - 0.01)]
            rings.append([(x, sy * (py + 0.035), pz) for py, pz in o] + [(x, sy * (py - 0.02), pz) for py, pz in reversed(o)])
        loft(f"SponsonPanel_{k_}_{sy}", rings, M["hull"] if k_ % 2 else M["hull_dark"], bevel=0.006)
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
# centre ridge running from the windshield base down the nose
loft("NoseRidge", [[(x, sy_ * w, deck(x) + dz) for sy_, w, dz in [(1, w0, 0.0), (1, w0 * 0.5, h), (-1, w0 * 0.5, h), (-1, w0, 0.0)]]
                   for x, w0, h in [(4.95, 0.2, 0.18), (5.5, 0.17, 0.2), (5.86, 0.14, 0.12)]], M["hull_dark"], bevel=0.01)
# rounded shoulder fairing between the side-window sill and the cheek top (front half of the hull)
for sy in (1, -1):
    rings = []
    for x in (5.0, 4.4, 3.4, 2.3, 1.7):
        zd = deck(x) + 0.02; zs = interp(SPON, x, 4) - 0.04; yo = interp(SPON, x, 2) - 0.08; yi = 1.0
        w_, h_ = yo - yi, zd - zs
        arc = [(yi, zd), (yi + 0.5 * w_, zd - 0.1 * h_), (yo - 0.04, zs + 0.38 * h_), (yo, zs + 0.12 * h_), (yo, zs)]
        pts = [(yi - 0.1, zd)] + arc + [(yi - 0.1, zs)]
        rings.append([(x, sy * py, pz) for py, pz in pts])
    loft(f"ShoulderFairing_{sy}", rings, M["hull"], bevel=0.01, smooth_angle=20)
# nose front frame + lights
box("NoseFrontFrame", (5.87, 0, -0.5), (0.06, 1.55, 0.5), M["hull_dark"], bevel=0.01)
box("NoseLight_A", (5.91, 0, -0.36), (0.03, 0.75, 0.06), M["glow"])
box("NoseLight_B", (5.91, 0, -0.48), (0.03, 0.45, 0.05), M["glow"])
for sy in (1, -1):
    # forward corner blocks flanking the nose face, each with a vertical lamp
    box(f"NoseCornerBlock_{sy}", (5.9, sy * 0.98, -0.47), (0.3, 0.24, 0.6), M["hull"], bevel=0.015, taper=(0.7, 0.8))
    box(f"NoseCornerLamp_{sy}", (6.06, sy * 0.98, -0.5), (0.03, 0.07, 0.22), M["glow"])
    box(f"NoseSideLamp_{sy}", (5.91, sy * 0.68, -0.46), (0.03, 0.05, 0.16), M["glow"])
    box(f"CheekLight_{sy}", (5.3, sy * 1.25, -0.52), (0.03, 0.34, 0.06), M["glow"], rot=(0, 0, sy * -1.0))
    box(f"CheekLamp_{sy}", (5.1, sy * 1.63, -0.42), (0.14, 0.03, 0.05), M["glow"])
loft("Chin", [[(x, sy * w, z) for sy, w, z in [(1, w0, zt), (1, w0 * 0.8, zb), (-1, w0 * 0.8, zb), (-1, w0, zt)]]
              for x, w0, zt, zb in [(5.86, 0.75, -0.74, -0.86), (5.2, 0.85, -0.9, -1.04), (4.6, 0.9, -1.0, -1.1)]], M["hull_dark"], bevel=0.01)
for sy in (1, -1):
    cyl(f"CannonShroud_{sy}", (5.98, sy * 0.2, -0.63), 0.085, 0.56, M["gun"], verts=12)
    cyl(f"CannonBarrel_{sy}", (6.6, sy * 0.2, -0.63), 0.035, 1.0, M["gun"], verts=10)
    cyl(f"CannonMuzzle_{sy}", (7.08, sy * 0.2, -0.63), 0.05, 0.1, M["gun"], verts=10)

# =================================================================== SUPERSTRUCTURE / CANOPY
# (x, halfwidth_bottom, z_top, top_width_factor) ; bottom follows the deck line
SUP = [(5.2, 1.04, 0.22, 0.82), (3.55, 1.18, 1.40, 0.74), (2.7, 1.22, 1.6, 0.72), (1.9, 1.25, 1.74, 0.71), (1.0, 1.27, 1.85, 0.7),
       (0.2, 1.28, 1.92, 0.7), (-1.0, 1.28, 1.97, 0.7), (-3.0, 1.25, 2.0, 0.7), (-3.8, 1.18, 1.88, 0.68), (-4.6, 1.02, 1.72, 0.66), (-5.2, 0.85, 1.5, 0.62)]
BAND = 0.10   # sloped roof-edge band above the windows
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
_wt = lambda x: zt_sup(x) - BAND - 0.02
# rear edge with the angled top-rear corner, top edge under the roof band, A-pillar edge, sill
SIDE_WIN = [(2.30, deck(2.3) + 0.16), (2.24, _wt(2.24) - 0.32), (2.52, _wt(2.52)), (3.5, _wt(3.5)), (4.35, _wt(4.35)), (4.85, deck(4.85) + 0.14)]  # rear, top, A-pillar edge, sill
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
WS = [(0.04, 0.95), (0.04, -0.95), (0.96, -0.92), (0.96, 0.92)]   # big trapezoid windshield, thin frame
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
WS_OUT = [(0.0, 0.99), (0.0, -0.99), (1.0, -0.96), (1.0, 0.96)]
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
def wall_plate(name, poly, sy, depth, mat):
    xm = sum(p_[0] for p_ in poly) / len(poly); zm = sum(p_[1] for p_ in poly) / len(poly)
    _, tilt = wall_y(xm, zm); nrm_ = Vector((0, sy * math.cos(tilt), math.sin(tilt)))
    pts = [Vector((cx, sy * (wall_y(cx, cz)[0] - 0.01), cz)) for cx, cz in poly]
    prism(f"{name}_{sy}", pts, nrm_ * depth, mat, bevel=0.006)
def frame_ring(name, poly, sy, width=0.06, depth=0.05, closed=True, mat=None):
    """strips lying flat on the tumblehome side wall along each polygon edge (no twisting)."""
    n = len(poly) if closed else len(poly) - 1
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(x1 - x0, z1 - z0); ux, uz = (x1 - x0) / L, (z1 - z0) / L
        e = width / 2; px, pz = -uz * e, ux * e  # in-plane perpendicular
        corners = [(x0 - ux * e + px, z0 - uz * e + pz), (x1 + ux * e + px, z1 + uz * e + pz),
                   (x1 + ux * e - px, z1 + uz * e - pz), (x0 - ux * e - px, z0 - uz * e - pz)]
        xm, zm = (x0 + x1) / 2, (z0 + z1) / 2
        _, tilt = wall_y(xm, zm)
        nrm_ = Vector((0, sy * math.cos(tilt), math.sin(tilt)))
        pts = [Vector((cx, sy * (wall_y(cx, cz)[0] - 0.01), cz)) for cx, cz in corners]
        prism(f"{name}_{i}_{sy}", pts, nrm_ * depth, mat or M["trim"], bevel=0.006)
for sy in (1, -1):
    frame_ring("FrameSide", SIDE_WIN, sy, width=0.045)
    frame_ring("FrameBay", BAY, sy, width=0.12, depth=0.07)
    # armour plates on the cabin wall: B-pillar block, and panels behind the bay
    wall_plate("BPillar", [(2.2, 0.5), (1.68, 0.5), (1.4, 1.58), (2.17, 1.62)], sy, 0.035, M["hull_dark"])
    frame_ring("AftPanel", [(-2.1, 0.5), (-3.9, 0.5), (-3.9, 1.6), (-2.1, 1.7)], sy, width=0.14, depth=0.04, mat=M["hull_dark"])

# =================================================================== SIMPLE CABIN (low detail by design)
def build_cabin():
    box("Cabin_Floor", (1.4, 0, 0.36), (7.0, 2.2, 0.04), M["interior"])
    box("Cabin_RearWall", (-1.95, 0, 1.15), (0.06, 2.3, 1.6), M["interior"])
    box("Cabin_Divider", (1.95, 0, 1.05), (0.06, 2.2, 1.4), M["interior"])
    box("Cabin_Spine", (-0.1, 0, 1.15), (3.4, 0.3, 1.6), M["interior"])
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
roof_plate("RoofSpine", 3.2, -1.9, 0.25, 0.1, M["hull_dark"])
# stepped blocks on the top rear behind the bay (stacked, each lower toward the cone)
def step_block(name, x0, x1, w, top, mat, chamf=0.15):
    poly = [(x0, zt_sup(x0) - 0.05), (x0 - chamf, top), (x1 + chamf, top), (x1, top - 0.15), (x1, zt_sup(x1) - 0.05)]
    side_prism(name, poly, -w, w, mat, bevel=0.015)
step_block("StepBlock_1", -1.9, -3.4, 0.86, 2.07, M["hull"])
step_block("StepBlock_2", -3.1, -4.4, 0.66, 1.95, M["hull_dark"])
step_block("StepBlock_3", -4.1, -5.15, 0.55, 1.76, M["hull"], chamf=0.2)
for sy in (1, -1):
    box(f"StepLamp_{sy}", (-2.7, sy * 0.87, 2.0), (0.25, 0.02, 0.04), M["glow"])
    box(f"StepLamp2_{sy}", (-4.6, sy * 0.56, 1.66), (0.2, 0.02, 0.04), M["glow"])
TX = -1.15; TZ = zt_sup(TX) + 0.1
cyl("Turret_Base", (TX, 0, TZ + 0.02), 0.36, 0.14, M["hull_dark"], axis="Z", verts=20)
cyl("Turret_Neck", (TX, 0, TZ + 0.1), 0.26, 0.08, M["trim"], axis="Z", verts=16)
def tur_ring(x, ry, rz, zc, n=12): return [(x, ry * math.cos(a), zc + rz * math.sin(a)) for a in [k * 2 * math.pi / n + math.pi / n for k in range(n)]]
TZC = TZ + 0.27
loft("Turret_Drum", [tur_ring(TX + dx, ry, rz, TZC) for dx, ry, rz in
                     [(0.62, 0.2, 0.13), (0.52, 0.3, 0.19), (0.3, 0.34, 0.21), (-0.4, 0.34, 0.21), (-0.55, 0.28, 0.17)]], M["hull"], bevel=0.01, smooth_angle=50)
for i, dx in enumerate((0.15, -0.15)):
    loft(f"Turret_Band_{i}", [tur_ring(TX + dx + d, 0.355, 0.225, TZC) for d in (0.05, -0.05)], M["hull_dark"])
box("Turret_TopPlate", (TX - 0.05, 0, TZC + 0.21), (0.7, 0.36, 0.04), M["hull_dark"], bevel=0.01)
box("Turret_Lamp", (TX + 0.05, 0.35, TZC), (0.18, 0.02, 0.04), M["glow"])
for sy in (1, -1):
    cyl(f"Turret_BarrelCollar_{sy}", (TX + 0.72, sy * 0.1, TZC - 0.02), 0.06, 0.22, M["gun"], verts=10)
    cyl(f"Turret_Barrel_{sy}", (TX + 1.2, sy * 0.1, TZC - 0.02), 0.03, 0.8, M["gun"], verts=10)
    cyl(f"Turret_Muzzle_{sy}", (TX + 1.58, sy * 0.1, TZC - 0.02), 0.045, 0.08, M["gun"], verts=10)

# =================================================================== REAR: conical tapered upper rear section (segmented)
# single cone continuing the cabin roof backwards (source: frame x 790-880, y 178-222)
CONE = [(-4.5, 0.95, 0.6, 1.12), (-5.0, 0.82, 0.52, 1.07), (-5.6, 0.66, 0.46, 1.03), (-6.4, 0.52, 0.4, 1.0),
        (-7.0, 0.42, 0.35, 0.98), (-7.33, 0.34, 0.3, 0.97), (-7.47, 0.2, 0.17, 0.97)]
def ell(x, ry, rz, zc, n=16): return [(x, ry * math.cos(a), zc + rz * math.sin(a)) for a in [k * 2 * math.pi / n for k in range(n)]]
loft("RearCone", [ell(*c) for c in CONE], M["hull"], bevel=0.01, smooth_angle=40)
for i, x in enumerate((-5.3, -5.95, -6.6, -7.2)):
    ry = interp(CONE, x, 1) * 1.07; rz = interp(CONE, x, 2) * 1.07; zc = interp(CONE, x, 3)
    loft(f"ConeBand_{i}", [ell(x + 0.09, ry * 0.97, rz * 0.97, zc), ell(x + 0.06, ry, rz, zc), ell(x - 0.06, ry, rz, zc), ell(x - 0.09, ry * 0.97, rz * 0.97, zc)], M["hull_dark"])
cyl("ConeGlow", (-7.48, 0, 0.97), 0.14, 0.02, M["engine"], verts=16)
# rear fuselage fairing under the cone: fills between cone, side bulges and wing roots so they read as one tapering mass
def oct_ring(x, hw, zb, zt):
    h = zt - zb
    pts = [(0.7, zb), (1.0, zb + 0.3 * h), (1.0, zb + 0.65 * h), (0.75, zt)]
    return [(x, hw * py, pz) for py, pz in pts] + [(x, -hw * py, pz) for py, pz in reversed(pts)]
loft("RearFairing", [oct_ring(*r_) for r_ in [(-3.9, 1.2, 0.05, 1.45), (-4.8, 1.1, -0.05, 1.2), (-5.8, 0.85, -0.1, 0.95), (-6.6, 0.55, 0.0, 0.8)]],
     M["hull"], bevel=0.012, smooth_angle=40)
for sy in (1, -1):
    box(f"ConeLamp_{sy}", (-6.25, sy * 0.5, 1.02), (0.3, 0.02, 0.04), M["glow"])

# =================================================================== REAR: side bulges / engine pods growing out of the hull taper
# (x, y_root, y_outer, z_bottom, z_top) - root is buried in the hull/cone so the form blends out of it
BULGE = [(-1.15, 1.2, 1.66, 0.22, 0.55), (-1.6, 1.15, 1.84, 0.0, 1.0), (-2.3, 1.1, 1.97, -0.16, 1.27), (-3.3, 1.0, 2.04, -0.22, 1.15),
         (-4.0, 0.88, 1.8, -0.24, 0.95), (-4.7, 0.75, 1.45, -0.2, 0.75), (-5.5, 0.55, 1.05, -0.1, 0.55), (-6.3, 0.35, 0.7, 0.0, 0.4)]
def bulge_ring(x, yi, yo, zb, zt, sy):
    w = yo - yi; h = zt - zb
    pts = [(yi, zb + 0.1 * h), (yi + 0.5 * w, zb), (yo - 0.1 * w, zb + 0.1 * h), (yo, zb + 0.32 * h), (yo, zb + 0.62 * h),
           (yo - 0.12 * w, zb + 0.86 * h), (yo - 0.38 * w, zt), (yi + 0.2 * w, zt - 0.1 * h), (yi, zt - 0.3 * h)]
    return [(x, sy * py, pz) for py, pz in pts]
for sy in (1, -1):
    loft(f"SideBulge_{sy}", [bulge_ring(*b, sy) for b in BULGE], M["hull"], bevel=0.015, smooth_angle=38)
    # layered shoulder plate along the bulge ridge
    loft(f"BulgePlate_{sy}", [[(x, sy * (yi + (yo - yi) * f), zb + (zt - zb) * g + dz) for f, g, dz in
                                [(0.3, 0.92, 0.0), (0.82, 0.92, 0.0), (0.8, 0.92, 0.06), (0.32, 0.92, 0.06)]]
                               for x, yi, yo, zb, zt in BULGE[1:6]], M["hull_dark"], bevel=0.008)
    # outer-face belt + amber marker + sign panel
    loft(f"BulgeBelt_{sy}", [[(x, sy * (yo + d), zb + (zt - zb) * f) for d, f in [(0.0, 0.36), (0.05, 0.4), (0.05, 0.56), (0.0, 0.6)]]
                              for x, yi, yo, zb, zt in BULGE[1:6]], M["hull_dark"], bevel=0.006)
    box(f"BulgeSign_{sy}", (-2.85, sy * 2.07, 0.3), (0.5, 0.02, 0.2), M["trim"])
    box(f"BulgeLamp_{sy}", (-2.4, sy * 1.99, 0.95), (0.22, 0.03, 0.05), M["glow"])
    box(f"BulgeLamp2_{sy}", (-3.6, sy * 1.92, 0.55), (0.3, 0.03, 0.04), M["glow"])
    # under-engine slung below the bulge, faired into it with a short pylon
    UY = sy * 1.85; UZ = -0.68
    cyl(f"UnderEngine_{sy}", (-3.85, UY, UZ), 0.25, 1.5, M["hull_dark"], verts=16)
    cyl(f"UnderEngineRing_{sy}", (-3.12, UY, UZ), 0.28, 0.1, M["trim"], verts=16)
    cyl(f"UnderEngineGlow_{sy}", (-3.06, UY, UZ), 0.19, 0.02, M["engine"], verts=16)
    cyl(f"UnderEngineNozzle_{sy}", (-4.65, UY, UZ), 0.2, 0.14, M["trim"], verts=16, r2=0.16)
    loft(f"UnderPylon_{sy}", [[(x, sy * (abs(UY) + dy), z) for dy, z in [(-0.08, UZ + 0.15), (0.08, UZ + 0.15), (0.12, -0.2), (-0.12, -0.2)]]
                              for x in (-3.4, -4.4)], M["hull_dark"], bevel=0.01)

# =================================================================== REAR WINGS: separate slabs projecting sideways from the hull
# span along +/-Y with slight sweep and dihedral; wedge section (front face with amber strips, top rising rearward)
WROOT, WTIP = 0.9, 3.32
WPROF = [(0.0, -0.32), (0.0, 0.36), (-0.15, 0.52), (-1.1, 0.86), (-1.3, 0.72), (-1.3, -0.32), (-0.9, -0.5)]
def wing_point(y, px, pz, sy=1):
    t = (y - WROOT) / (WTIP - WROOT); k = 1.0 - 0.48 * t
    xle = -4.0 - (y - 1.6) * (1.65 / 2.15); dz = 0.04 * max(t, 0)
    return (xle + px * k, sy * y, dz + pz * k)
def wing_section(y, sy, dx=0.0, scale=1.0):
    return [(wing_point(y, px * scale, pz * scale, sy)[0] + dx, sy * y, wing_point(y, px * scale, pz * scale, sy)[2]) for px, pz in WPROF]
for sy in (1, -1):
    loft(f"RearWing_{sy}", [wing_section(y, sy) for y in (WROOT, 2.0, 2.8, 2.98)], M["hull"], bevel=0.012)
    # tip block: slightly larger section, with lamps on its front face
    loft(f"WingTipBlock_{sy}", [wing_section(y, sy, dx=0.04, scale=1.08) for y in (2.93, WTIP)], M["hull_dark"], bevel=0.015)
    for z_off in (0.18, 0.02):
        a = wing_point(3.17, 0.08, z_off * 0.7, sy); box(f"WingTipLamp_{z_off}_{sy}", a, (0.03, 0.38, 0.045), M["glow"], rot=(0, 0, sy * 0.54))
    # recessed slot on the front face + amber strips (twin bars like the source)
    for i, (ya, yb) in enumerate([(1.5, 2.15), (2.25, 2.85)]):
        ym = (ya + yb) / 2; L = (yb - ya) / math.cos(0.54)
        a = wing_point(ym, 0.02, 0.1, sy)
        box(f"WingSlot_{i}_{sy}", a, (0.05, L + 0.1, 0.24), M["trim"], rot=(0, 0, sy * 0.54))
        b = wing_point(ym, 0.05, 0.1, sy)
        box(f"WingStrip_{i}_{sy}", b, (0.03, L - 0.1, 0.05), M["glow"], rot=(0, 0, sy * 0.54))
    # top armour plate on the wing
    loft(f"WingTopPlate_{sy}", [[wing_point(y, px, pz + dz, sy) for px, pz, dz in [(-0.25, 0.57, 0.0), (-1.0, 0.83, 0.0), (-1.0, 0.83, 0.05), (-0.25, 0.57, 0.05)]]
                                for y in (1.4, 2.95)], M["hull_dark"], bevel=0.006)

# =================================================================== hull / cabin light strips
for sy in (1, -1):
    for i, (x, f, L) in enumerate([(3.6, 0.52, 0.7), (1.4, 0.52, 0.9), (-0.7, 0.52, 0.7), (2.5, 0.15, 0.5), (-1.4, 0.15, 0.6)]):
        yo = interp(SPON, x, 2); zb = interp(SPON, x, 3); zt = interp(SPON, x, 4)
        box(f"HullStrip_{i}_{sy}", (x, sy * (yo + 0.06), zb + (zt - zb) * f), (L, 0.03, 0.045), M["glow"])
    for i, x in enumerate((4.0, 2.6, 0.9, -2.6)):
        y, _ = wall_y(x, deck(x) + 0.05)
        box(f"ShellLamp_{i}_{sy}", (x, sy * (y + 0.01), deck(x) + 0.08), (0.2, 0.03, 0.04), M["glow"])

# belly: keel plate + layered panels so the underside isn't a blank blob
loft("BellyKeel", [[(x, sy_ * w, zb_at(x) + dz) for sy_, w, dz in [(1, 0.32, 0.02), (1, 0.26, -0.07), (-1, 0.26, -0.07), (-1, 0.32, 0.02)]]
                   for x in (4.4, 3.0, 1.0, -1.0, -3.0, -4.6)], M["hull_dark"], bevel=0.01)
for sy in (1, -1):
    for i, (x0, x1) in enumerate([(4.2, 2.6), (2.4, 0.5), (0.3, -1.6), (-1.8, -3.8)]):
        rings = [[(x, sy * w, zb_at(x) + dz) for w, dz in [(0.42, 0.01), (0.42, -0.035), (0.6 * hw_at(x) - 0.02, -0.035), (0.6 * hw_at(x) - 0.02, 0.01)]] for x in (x0, x1)]
        loft(f"BellyPanel_{i}_{sy}", rings, M["hull"] if i % 2 else M["hull_dark"], bevel=0.006)
    for x in (3.4, 0.0, -3.2):
        box(f"BellyLamp_{x}_{sy}", (x, sy * 0.9 * hw_at(x), zb_at(x) + 0.12), (0.35, 0.03, 0.04), M["glow"])

# main rear: tapered lower hull end with recessed exhausts
for sy in (1, -1):
    cyl(f"MainNozzle_{sy}", (-6.32, sy * 0.25, -0.15), 0.16, 0.14, M["trim"], verts=16, r2=0.19, cap=False)
    cyl(f"MainGlow_{sy}", (-6.31, sy * 0.25, -0.15), 0.15, 0.02, M["engine"], verts=16)

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
                    "preview_rear34": dict(yaw=-130, pitch=18, dist=27, lens=60, tz=0.2, tx=-0.6),
                    "preview_top": dict(yaw=0, pitch=89.5, dist=30, lens=60, tx=-0.6, roll=0),
                    "preview_under": dict(yaw=30, pitch=-35, dist=27, lens=60, tz=0.0, tx=-0.6),
                    "preview_back": dict(yaw=-90, pitch=10, dist=27, lens=60, tz=0.3, tx=0)}.items():
        if name in ("preview_under", "preview_back") and "--extra" not in argv: continue
        place_cam(**c); render(os.path.join(OUT, name + SUFFIX + ".png"))
