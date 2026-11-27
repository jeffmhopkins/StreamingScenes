"""Procedural spaceship builder (round 13: 9-pod cold-gas RCS at the extremities; round 12: crease-aware conforming plates [overlap fix], plain-side armour detail, convention nav lights; on top of r11 cleanup/refine).
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
SAMPLES = arg("--samples", 64); SUFFIX = arg("--suffix", "_r13")
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
    "engine_aft": bsdf_mat("EngineGlowAft", (1.0, 0.42, 0.08), 0, 0.4, emit=(1.0, 0.42, 0.08), emit_strength=4),
    "nav_red": bsdf_mat("NavRed", (0.35, 0.0, 0.0), 0, 0.3, emit=(1.0, 0.0, 0.0), emit_strength=3.5),
    "nav_green": bsdf_mat("NavGreen", (0.0, 0.35, 0.04), 0, 0.3, emit=(0.0, 1.0, 0.12), emit_strength=3.0),
    "nav_white": bsdf_mat("NavWhite", (1.0, 1.0, 1.0), 0, 0.3, emit=(1.0, 0.97, 0.9), emit_strength=10),
    "glass_dark": bsdf_mat("WindowDarkGlass", (0.008, 0.012, 0.016), 0.0, 0.06),
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
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)          # r11: merge coincident verts
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)     # r11: drop zero-area slivers
    if recalc: bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    smooth_angle = min(smooth_angle, 30)                              # r11: steel plates -- crisp hard edges, flat-shaded faces
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
        md = ob.modifiers.new("Bevel", "BEVEL"); md.width = bevel; md.segments = 1
        md.limit_method = "ANGLE"; md.angle_limit = math.radians(30); md.harden_normals = True
    wn = ob.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"); wn.keep_sharp = True; wn.weight = 50
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
        zd = deck(x) + 0.015; zs = interp(SPON, x, 4) - 0.04   # r12b diag Z1/Z2: was coplanar with the shell cavity floor; yo = interp(SPON, x, 2) - 0.08; yi = 1.0
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
# r6: side cockpit window retraced (side_window_edges_r6.png): front edge runs right behind the A-pillar (parallel to it)
# from the sill up to the roof band, top edge under the roof band, angled top-rear corner, short rear edge, and a sill that
# rises from the pillar foot then breaks upward at the angled rear-bottom edge.
SIDE_WIN = [(2.26, 0.86), (2.19, _wt(2.19) - 0.08), (2.31, _wt(2.31)), (3.42, _wt(3.42)), (4.83, deck(4.83) + 0.07), (3.36, 0.5)]
BAY = [(1.60, 0.46), (1.25, 1.50), (1.00, 1.66), (-1.30, 1.66), (-1.85, 1.12), (-1.75, 0.42)]
cutters = [cavity]
for sy in (1, -1):
    cutters.append(side_prism(f"cut_side_{sy}", SIDE_WIN, sy * 0.45, sy * 2.5, None, parent=None))
    # r9: mid bay opening closed (solid hull); small slatted windows are added on the wall below
A, B = SUP[0], SUP[1]  # windshield = sloped top face between ring B (top, X=3.0) and ring A (bottom, X=4.48)
def on_slope(u, v):
    x = lerp(B[0], A[0], u); w = lerp(B[1] * B[3], A[1] * A[3], u); z = lerp(B[2], A[2], u)
    return Vector((x, v * w, z))
nrm = (on_slope(1, 1) - on_slope(0, 1)).cross(on_slope(0, -1) - on_slope(0, 1)).normalized()
if nrm.z < 0: nrm = -nrm
# --- windshield (r5: rebuilt from the edge trace in windshield_edges_r5.png)
# Read from the reference: one big flat pane on the sloped front face (glass corners at u~0.05/0.93, |v|~0.92 of the face),
# a thin dark outer frame with a second inner frame line (lip), a narrow header under the roof edge, a sill at the bottom,
# and a broad light A-pillar bar wrapping each front/side corner onto the side wall.
WS_U0, WS_U1, WS_V = 0.05, 0.93, 0.92
WS = [(WS_U0, WS_V), (WS_U0, -WS_V), (WS_U1, -WS_V), (WS_U1, WS_V)]
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
def ws_poly(u0, u1, v): return [on_slope(u0, v), on_slope(u0, -v), on_slope(u1, -v), on_slope(u1, v)]
# r12b: windshield frame = header strip + sill strip only; the side strips are now the A-pillars themselves (built after wpt()),
# so frame and pillar butt-join flush instead of overlapping (old: ring frame + inner lip + header bar + slab pillar all stacked).
def ws_strip(name, u0, u1, vv=1.0):
    return prism(name, [on_slope(u, v) - nrm * 0.01 for u, v in ((u0, -vv), (u0, vv), (u1, vv), (u1, -vv))], nrm * 0.05, M["trim"], bevel=0.006)
ws_strip("WindshieldFrame", 0.0, WS_U0)     # r12b diag P30: started at u=-0.03 where the roof rises above the slope plane
ws_strip("WindshieldSill", WS_U1, 0.995, vv=0.99)   # r12b diag P19: end trimmed off the canopy corner
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
    # r10: plate conforms to the tumblehome wall per vertex (the old single-tilt prism stood proud of the wall at the top)
    def pt(x, z, d):
        y, tilt = wall_y(x, z); return (x, sy * (y - 0.006 + d * math.cos(tilt)), z + d * math.sin(tilt))
    loft(f"{name}_{sy}", [[pt(x, z, d) for x, z in poly] for d in (-0.004, depth)], mat, bevel=0.006)
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
BAY_WINS = [(1.28, 0.56), (0.24, -0.48), (-0.8, -1.52)]; BAY_Z0, BAY_Z1 = 1.0, 1.44
def bay_poly(x0, x1):   # CCW in (x, z) seen from +Y: chamfered front-top and rear-bottom corners
    z0, z1 = BAY_Z0, BAY_Z1
    return [(x0, z0), (x0, z1 - 0.11), (x0 - 0.11, z1), (x1, z1), (x1, z0 + 0.08), (x1 + 0.08, z0)]
def offset_poly(poly, d):   # outward offset of a convex polygon
    n = len(poly); sgn = 1 if sum((poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1]) for i in range(n)) > 0 else -1
    lines = []
    for i in range(n):
        (ax, az), (bx, bz) = poly[i], poly[(i + 1) % n]; L = math.hypot(bx - ax, bz - az)
        nx, nz = sgn * (bz - az) / L, -sgn * (bx - ax) / L
        lines.append(((ax + nx * d, az + nz * d), (bx - ax, bz - az)))
    out = []
    for i in range(n):
        (p1, d1), (p2, d2) = lines[i - 1], lines[i]
        den = d1[0] * d2[1] - d1[1] * d2[0]
        t_ = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
        out.append((p1[0] + d1[0] * t_, p1[1] + d1[1] * t_))
    return out
def poly_span(poly, za, zb):   # x-range inside the polygon valid for every z in [za, zb]
    lo, hi = -1e9, 1e9
    for z in (za, (za + zb) / 2, zb):
        xs = []
        n = len(poly)
        for i in range(n):
            (ax, az), (bx, bz) = poly[i], poly[(i + 1) % n]
            if (az - z) * (bz - z) <= 0 and az != bz: xs.append(ax + (bx - ax) * (z - az) / (bz - az))
        lo = max(lo, min(xs)); hi = min(hi, max(xs))
    return hi, lo   # (front x, rear x)
def wpt(x, z, sy, d):   # point on the tumblehome side wall, offset d along the wall normal
    y, tilt = wall_y(x, z)
    return (x, sy * (y - 0.005 + d * math.cos(tilt)), z + d * math.sin(tilt))
# r12b (markup_apillar_r12): A-pillar rebuilt as ONE continuous frame member per side: from the windshield glass edge over the
# canopy corner and the roof band down the side wall to the side-window frame. Its windshield edge is flush with the header/sill
# strips (top +0.04 on the slope), its wall edge ends exactly at the side-window frame's outer edge (offset 0.05, +0.022), so both
# window frames join into it; no glass under it, no stacked strips.
_off = offset_poly(SIDE_WIN, 0.05); (_fx0, _fz0), (_fx1, _fz1) = _off[3], _off[4]
def _front_z(x): return _fz0 + (_fz1 - _fz0) * (x - _fx0) / (_fx1 - _fx0)
for sy in (1, -1):
    rings = []
    for u in [lerp(WS_U0, WS_U1, k / 8) for k in range(9)]:
        x = lerp(B[0], A[0], u); hw, zt, tf = interp(SUP, x, 1), interp(SUP, x, 2), interp(SUP, x, 3); zb = deck(x) - 0.04
        k_ = min(1.0, (zt - zb) / 0.6)
        g0 = on_slope(u, sy * WS_V); c0 = on_slope(u, sy * 1.0)
        p2 = Vector((x, sy * hw * (tf + 0.1), zt - BAND * k_))                       # band / wall break (shell ring point 2)
        zf = max(_front_z(x), zb + 0.1 * k_ + 0.03); zf = min(zf, p2.z - 0.02)
        sn = Vector((0, sy * 0.85, 0.52)).normalized(); cn = (nrm + sn).normalized()
        bn = (c0 - p2).cross(Vector((1, 0, 0))); bn = bn.normalized() * (1 if bn.dot(Vector((0, sy, 0.3))) > 0 else -1)   # band normal
        w3 = Vector(wpt(x, zf, sy, 0.022)); w3i = Vector(wpt(x, zf, sy, -0.012))
        rings.append([g0 + nrm * 0.04, c0 + cn * 0.04, p2 + bn * 0.03, w3, w3i, p2 - bn * 0.012, c0 - cn * 0.012, g0 - nrm * 0.01])
    loft(f"APillar_{sy}", rings, M["hull"], bevel=0.006, smooth_angle=20)
for sy in (1, -1):
    # r11: side cockpit window frame as one continuous chamfered loft (was 6 overlapping strips)
    loft(f"FrameSide_{sy}", [[wpt(x, z, sy, d) for x, z in pg] for pg, d in ((offset_poly(SIDE_WIN, 0.05), -0.012), (offset_poly(SIDE_WIN, 0.05), 0.022),
                              (offset_poly(SIDE_WIN, 0.032), 0.032), (offset_poly(SIDE_WIN, -0.004), 0.0), (offset_poly(SIDE_WIN, -0.004), -0.07))], M["trim"], cap=False, smooth_angle=20)
    # r10: closed mid bay -- three small windows properly recessed into the armoured wall: hole cut in the shell, chamfered
    # frame sloping into the recess, evenly spaced angled louvers sitting inside the recess, dark glass at the back
    for k_, (x0, x1) in enumerate(BAY_WINS):
        win = bay_poly(x0, x1)
        cut = side_prism(f"cut_baywin_{k_}_{sy}", [(x, z) for x, z in win], sy * 0.6, sy * 2.5, None, parent=None)
        cut.hide_render = True; cutters.append(cut)
        if "--nobool" not in argv: boolean(shell, cut)
        rings = [[wpt(x, z, sy, d) for x, z in pg] for pg, d in ((offset_poly(win, 0.085), -0.012), (offset_poly(win, 0.085), 0.018),
                                                                    (offset_poly(win, 0.06), 0.03), (offset_poly(win, -0.004), -0.035), (offset_poly(win, -0.004), -0.11))]
        loft(f"BayWinFrame_{k_}_{sy}", rings, M["hull_dark"], cap=False, smooth_angle=20)
        loft(f"BayWinGlass_{k_}_{sy}", [[wpt(x, z, sy, d) for x, z in offset_poly(win, 0.01)] for d in (-0.1, -0.11)], M["glass_dark"])
        zs = [lerp(BAY_Z0 + 0.06, BAY_Z1 - 0.06, j_ / 4) for j_ in range(5)]
        for j_, z in enumerate(zs):   # louvers: 5 evenly spaced, angled down-out, inside the recess between the frame walls
            xa, xb = poly_span(win, z - 0.03, z + 0.03)
            sec = lambda x: [wpt(x, z + 0.028, sy, -0.085), wpt(x, z + 0.04, sy, -0.075), wpt(x, z - 0.02, sy, -0.04), wpt(x, z - 0.032, sy, -0.05)]
            loft(f"BayLouver_{k_}_{j_}_{sy}", [sec(xa - 0.004), sec(xb + 0.004)], M["hull"], smooth_angle=20)
    # armour on the closed wall: lower belt plate with a lamp strip, thin upper plate band (lined up with the window tops)
    wall_plate("BayBelt", [(1.62, 0.52), (-1.86, 0.52), (-1.86, 0.80), (1.5, 0.80)], sy, 0.035, M["hull_dark"])   # r12b diag P12/13: top edge was a sliver along the bulge
    wall_plate("BayUpperPlate", [(1.36, 1.58), (-1.7, 1.58), (-1.7, 1.68), (1.3, 1.68)], sy, 0.025, M["hull_dark"])
    wall_plate("BayBeltLamp", [(0.9, 0.66), (-0.9, 0.66), (-0.9, 0.705), (0.9, 0.705)], sy, 0.05, M["glow"])
    # armour plates on the cabin wall: B-pillar block, and panels behind the bay
    wall_plate("BPillar", [(2.2, 0.5), (1.68, 0.5), (1.43, 1.5), (2.17, 1.52)], sy, 0.035, M["hull_dark"])   # r10: kept below the roof band so it lies on the wall
    # r10: aft armour panel as one flush wall-conforming plate (its old frame strips read as a post poking through the hull)
    # r12b diag P01/P02: lofted along x through the shell's ring stations (and 5 rows in z) so it follows the wall kinks at
    # x=-3.0/-3.8 instead of bridging them (the shell sliced up through the old 4-corner plate)
    def _apt(x, z, d):
        y, tilt = wall_y(x, z); return (x, sy * (y - 0.006 + d * math.cos(tilt)), z + d * math.sin(tilt))
    _rows = [0.5 + (1.0 * k / 5) for k in range(6)]
    _rings = []
    for x in (-2.0, -2.5, -3.0, -3.4, -3.8, -3.9):
        ztop = 1.66 + (1.6 - 1.66) * (x + 2.0) / -1.9; zs_ = [0.5 + (ztop - 0.5) * k / 5 for k in range(6)]
        _rings.append([_apt(x, z, 0.03) for z in zs_] + [_apt(x, z, -0.008) for z in reversed(zs_)])
    loft(f"AftPanel_{sy}", _rings, M["hull_dark"], bevel=0.006)

# =================================================================== SIMPLE CABIN (low detail by design)
def build_cabin():
    box("Cabin_Floor", (1.4, 0, 0.36), (7.0, 2.2, 0.04), M["interior"])
    # r10: bay rear wall removed (bay is closed; it poked through the tumblehome wall below the turret)
    box("Cabin_Divider", (1.95, 0, 0.975), (0.06, 1.6, 1.2), M["interior"])   # r10: shrunk to sit inside the shell (was poking through)
    for sy in (1, -1):
        box(f"Seat_{sy}", (3.0, sy * 0.45, 0.55), (0.45, 0.42, 0.35), M["interior"])
        box(f"SeatBack_{sy}", (2.75, sy * 0.45, 0.85), (0.08, 0.42, 0.6), M["interior"])
        yw_, tl_ = wall_y(3.1, 0.95)
        box(f"CockpitScreen_{sy}", (3.1, sy * (yw_ - 0.094), 0.95), (0.55, 0.012, 0.32), M["screen"], rot=(sy * tl_, 0, 0))   # r11: on the inner wall
    box("Cockpit_Console", (4.15, 0, 0.45), (0.8, 1.5, 0.3), M["interior"], taper=(0.6, 1))
    box("Cockpit_CeilingLight", (2.8, 0, 1.47), (0.8, 0.08, 0.02), M["cabinlight"])   # r11: was poking into the roof shell
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
# r8: StepBlock_2/3 removed (aft section redesigned below)
for sy in (1, -1):
    box(f"StepLamp_{sy}", (-2.7, sy * 0.87, 2.0), (0.25, 0.02, 0.04), M["glow"])
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

# =================================================================== REAR BULGE + WING (r7: one continuous form fitted to the owner's red lines)
# Every edge below was back-projected from the owner's strokes (user_edges_registered_r6.png) through the matching camera
# (work5/fitwing.py).  Leading-edge depth rule: X=-3.5 where the upper red line leaves the hull roof edge (Y 0.78), sliding
# to X=-4.1 at the bulge's outer-top corner (Y 2.5), then straight out (constant X) to the tip.
#  upper red line  -> leading top edge of the wing (R1): starts on the hull roof edge, runs down over the bulge, then out to the tip
#  second red line -> lower edge of the root chamfer band (R2) where the band meets the bulge top
#  red box         -> slot plate on the wing's tall leading face (BT/BB), cyan bottom stroke -> wing leading bottom edge (WB)
#  orange          -> crest of the wing top (X -5.0) and the raked tip end; cyan bulge contour -> bulge outer-top edge
def XL(y): return -3.5 if y <= 0.8 else (-3.5 - 0.6 * (y - 0.8) / 1.7 if y < 2.5 else -4.1)
def tbl(t, y): return interp([(-a_, b_) for a_, b_ in t], -y, 1)
R1 = [(0.55, 2.0), (0.75, 2.0), (1.0, 1.82), (1.25, 1.61), (1.45, 1.44), (1.6, 1.27), (1.95, 1.24), (2.17, 1.15), (2.4, 0.94), (2.52, 0.80), (3.0, 0.77),
      (3.5, 0.72), (4.0, 0.69), (4.43, 0.65), (4.88, 0.64)]
R2 = [(0.55, 1.58), (0.73, 1.49), (0.87, 1.42), (0.99, 1.24), (1.1, 1.07), (1.45, 1.03), (1.8, 0.81)]
BT = [(2.09, 0.52), (2.55, 0.51), (3.11, 0.47), (3.7, 0.47)]
BB = [(2.06, -0.09), (2.51, -0.1), (3.13, -0.05), (3.7, 0.03)]
WB = [(0.55, 0.75), (0.75, 0.55), (1.4, 0.05), (2.08, -0.29), (2.3, -0.255), (2.53, -0.15), (2.99, -0.08), (3.51, -0.02), (3.99, 0.05), (4.25, 0.15), (4.51, 0.22),
      (4.76, 0.31), (4.88, 0.35)]
WTIP = 4.88
TIPY = 4.98   # r9: outer face of the squared tip block
def crest_z(y):   # wing-top crest at X -5.0 (orange stroke)
    zt = tbl(R1, y)
    if y < 2.0: return zt - 0.05
    if y <= 3.0: return min(zt + 0.03, 0.84)
    return lerp(min(zt + 0.03, 0.84), zt - 0.05, min(1.0, (y - 3.0) / 0.4))
LIP_X, LIP_T, CH_BW, CH_Y0, CH_Y1 = -5.72, 0.04, -5.45, 2.36, 4.45   # r10 trailing-edge engine channel
def ch_open(y, grow):   # (z_low, z_high) of the channel opening between the lips at span y
    zt = tbl(R1, y) + grow; zb = tbl(WB, y) - grow; ttop = zt - 0.25; tbot = min(zb + 0.2, ttop - 0.3)
    return tbot + LIP_T, ttop - LIP_T
def ylim(x, y): return y    # r8: square tip (owner markup_top_r7: no sweep, tip edge runs fore-aft, trailing edge straight in)
def wing_sec7(y, sy, grow=0.0):
    xl = XL(y) + grow; zt = tbl(R1, y) + grow; zb = tbl(WB, y) - grow
    zc = tbl(R2, y) if y <= 1.8 else lerp(tbl(R2, 1.8), zt - 0.12, min(1.0, (y - 1.8) / 0.7))
    ttop = zt - 0.25; tbot = min(zb + 0.2, ttop - 0.3)   # r9: trailing face never collapses toward the tip
    t = LIP_T
    if CH_Y0 <= y <= CH_Y1:   # r10: top & bottom skins run out to LIP_X as lips; engine bank recessed to the back wall CH_BW
        rear = [(LIP_X, ttop), (LIP_X, ttop - t), (CH_BW, ttop - t), (CH_BW, tbot + t), (LIP_X, tbot + t), (LIP_X, tbot)]
    else:                     # plain flat trailing face (root region), same vertex count
        xr = -5.6 - grow; h = ttop - tbot
        rear = [(xr, ttop), (xr, ttop - 0.2 * h), (xr, ttop - 0.4 * h), (xr, tbot + 0.4 * h), (xr, tbot + 0.2 * h), (xr, tbot)]
    pts = [(xl + 0.07, zc), (xl, zt), (-5.0, crest_z(y) + grow)] + rear + [(xl - 0.25, zb), (xl + 0.05, zb + 0.08)]
    return [(px, sy * ylim(px, y), pz) for px, pz in pts]
# bulge: cone growing out of the hull flank into a faceted shoulder whose outer-top edge (cyan) rises into the wing kink
BUL = [(-1.67, -0.30, 0.0, 0.46, 0.95), (-2.3, -0.35, 0.0, 0.62, 1.02), (-2.9, -0.40, 0.0, 0.73, 1.06), (-3.4, -0.18, 0.0, 0.78, 1.07),
       (-4.0, -0.15, 0.05, 0.79, 1.05), (-4.5, -0.05, 0.1, 0.7, 0.95)]   # (x, z_bottom, z_lower_chine, z_outer_top, z_inner_top)
BUL_LOW = {-3.4: (2.3, 0.1), -4.0: (2.0, 0.5), -4.5: (1.9, 0.5)}   # rear undercut: (outer Y of the lower face, chine Z)
def bul_sec(x, zb, zch, zo, zti, sy, yo=2.5, yi=1.15, s_=1.0, c=(1.3, 0.3)):
    yl, zch = BUL_LOW.get(x, (yo, zch))
    pts = [(yi, zb + 0.25), (yi + 0.3, zb), (yl - 0.25, zb), (yl, zch), (yo, zo), (yo - 0.35, zo + 0.17), (yi + 0.55, zti), (yi, zti - 0.05)]
    return [(x, sy * (c[0] + s_ * (py - c[0])), c[1] + s_ * (pz - c[1])) for py, pz in pts]
for sy in (1, -1):
    Y = lambda y: sy * y
    f0 = BUL[0]
    rings = [bul_sec(x, *f0[1:], sy, s_=s_) for x, s_ in ((0.05, 0.08), (-0.45, 0.5), (-1.05, 0.84))]
    rings += [bul_sec(*b_, sy, yo=(2.5 if b_[0] > -4.2 else 2.3)) for b_ in BUL]
    loft(f"Bulge_{sy}", rings, M["hull"], bevel=0.01, smooth_angle=25)
    for i, (x, s_) in enumerate(((-1.05, 0.84), (-1.67, 1.0), (-2.3, 1.0))):   # yellow cross-section ribs
        prm = (f0[1:] if s_ < 1 else [interp(BUL, x, k) for k in (1, 2, 3, 4)])
        loft(f"BulgeRib_{i}_{sy}", [bul_sec(x + d, *prm, sy, s_=s_ * g, yo=2.5) for d, g in ((0.04, 1.0), (0.025, 1.03), (-0.025, 1.03), (-0.04, 1.0))], M["hull_dark"])
    box(f"PodSign_{sy}", (-1.9, Y(2.51), 0.22), (0.5, 0.03, 0.18), M["trim"]); box(f"PodSignGlow_{sy}", (-1.9, Y(2.525), 0.22), (0.36, 0.01, 0.05), M["glow"])
    box(f"PodFwdLamp_{sy}", (-2.55, Y(2.515), 0.3), (0.04, 0.02, 0.18), M["glow"])
    box(f"PodBodyLamp_{sy}", (-3.0, Y(2.25), 0.86), (0.28, 0.03, 0.04), M["glow"], rot=(0.45 * sy, 0, 0))
    # wing: one loft from the hull roof edge, over the bulge, out to the tip
    WY = [0.55, 0.75, 1.0, 1.25, 1.45, 1.6, 1.95, 2.17, 2.34, 2.36, 2.4, 2.52, 3.0, 3.5, 3.72]
    loft(f"Wing_{sy}", [wing_sec7(y, sy) for y in WY], M["hull"], bevel=0.01, smooth_angle=30)
    loft(f"WingTip_{sy}", [wing_sec7(y, sy, grow=0.03) for y in (3.7, 4.0, 4.4)], M["hull_dark"], bevel=0.01, smooth_angle=30)
    # r9: clean squared wing-tip block (replaces the collapsed rear tip corner)
    TB = [(-4.0, 0.16), (-4.0, 0.64), (-4.08, 0.72), (-5.62, 0.68), (-5.72, 0.58), (-5.72, 0.18), (-5.64, 0.08), (-4.08, 0.08)]
    tbc = (-4.86, 0.4)
    loft(f"WingTipBlock_{sy}", [[(tbc[0] + (x - tbc[0]) * k, Y(y), tbc[1] + (z - tbc[1]) * k) for x, z in TB]
                                for y, k in ((4.32, 1.0), (4.92, 1.0), (TIPY, 0.9))], M["hull_dark"], bevel=0.012, smooth_angle=30)
    loft(f"WingTipBand_{sy}", [[(tbc[0] + (x - tbc[0]) * k, Y(y), tbc[1] + (z - tbc[1]) * k) for x, z in TB]
                               for y, k in ((4.6, 1.0), (4.62, 1.03), (4.7, 1.03), (4.72, 1.0))], M["trim"])
    # r12: amber WingTipOuterLamp removed -- the tip now carries the red/green sidelight
    # r10: inset engine bank in the trailing-edge channel: dark back wall, divider ribs, six rectangular ion-grid nozzles
    def gz(y): return 0.03 if y > 3.71 else 0.0
    def chz(y): return ch_open(y, gz(y))
    ys_ = [lerp(CH_Y0, 4.32, k / 6) for k in range(7)]
    loft(f"EngineBankWall_{sy}", [[(CH_BW - 0.005, Y(y), chz(y)[0] - 0.005), (CH_BW - 0.005, Y(y), chz(y)[1] + 0.005), (CH_BW + 0.02, Y(y), chz(y)[1] + 0.005), (CH_BW + 0.02, Y(y), chz(y)[0] - 0.005)]
                                  for y in (CH_Y0, 2.4, 2.52, 3.0, 3.5, 3.72, 4.0, 4.32)], M["trim"])
    for k_, y in enumerate(ys_[1:-1]):   # divider ribs between units, flush with the lip ends
        zl, zh = chz(y)
        box(f"EngineBankRib_{k_}_{sy}", ((CH_BW + LIP_X) / 2 - 0.005, Y(y), (zl + zh) / 2), (LIP_X - CH_BW - 0.0, 0.035, zh - zl + 0.01), M["hull_dark"], bevel=0.004)
    for k_, (ya, yb) in enumerate(zip(ys_, ys_[1:])):
        ya2, yb2 = ya + 0.03, yb - 0.03
        zl = max(chz(ya2)[0], chz(yb2)[0], chz((ya2 + yb2) / 2)[0]) + 0.015
        zh = min(chz(ya2)[1], chz(yb2)[1], chz((ya2 + yb2) / 2)[1]) - 0.015
        ym, zm, hy, hz = (ya2 + yb2) / 2, (zl + zh) / 2, (yb2 - ya2) / 2, (zh - zl) / 2
        def rr(x, d): return [(x, Y(ym + sy_ * (hy - d)), zm + sz_ * (hz - d)) for sy_, sz_ in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
        # flared rectangular nozzle: narrow throat at the back wall, flares to the exit just inside the lips
        loft(f"IonNozzle_{k_}_{sy}", [rr(CH_BW - 0.01, 0.035), rr(-5.67, 0.0), rr(-5.67, 0.022), rr(CH_BW - 0.03, 0.06)], M["hull_dark"], cap=False, bevel=0.003)
        box(f"IonGlowPlate_{k_}_{sy}", (CH_BW - 0.035, Y(ym), zm), (0.01, 2 * (hy - 0.062), 2 * (hz - 0.062)), M["engine_aft"])
        nv = 2 if hz < 0.16 else 3
        for j_ in range(nv):   # horizontal grid vanes
            z = zm - hz + 2 * hz * (j_ + 1) / (nv + 1)
            box(f"IonVane_{k_}_{j_}_{sy}", (-5.56, Y(ym), z), (0.2, 2 * (hy - 0.03), 0.012), M["trim"])
        box(f"IonBar_{k_}_{sy}", (-5.555, Y(ym), zm), (0.2, 0.014, 2 * (hz - 0.03)), M["trim"])
    # slot plate on the leading face (the red box), twin amber strips, divider ribs
    loft(f"WingSlot_{sy}", [[(XL(y) + 0.085, Y(y), tbl(BB, y)), (XL(y) + 0.085, Y(y), tbl(BT, y)), (XL(y) + 0.0, Y(y), tbl(BT, y)), (XL(y) + 0.0, Y(y), tbl(BB, y))]
                            for y in (2.06, 2.3, 2.52, 3.1, 3.7)], M["trim"])
    for i, (ya, yb) in enumerate([(2.15, 2.75), (2.95, 3.55)]):
        ym = (ya + yb) / 2; zm = lerp(tbl(BB, ym), tbl(BT, ym), 0.45)
        box(f"WingStrip_{i}_{sy}", (-4.1 + 0.095, Y(ym), zm), (0.02, yb - ya, 0.06), M["glow"])
    for i, y in enumerate((2.08, 2.85, 3.68)):
        box(f"WingSlotRib_{i}_{sy}", (XL(y) + 0.09, Y(y), (tbl(BB, y) + tbl(BT, y)) / 2), (0.05, 0.07, tbl(BT, y) - tbl(BB, y)), M["hull_dark"])
    for i, z in enumerate((0.51, 0.42)):
        box(f"WingTipLamp_{i}_{sy}", (-3.985, Y(4.54), z), (0.02, 0.18, 0.04), M["glow"])
    box(f"WingTipSeam_{sy}", (-3.99, Y(4.41), 0.36), (0.02, 0.03, 0.3), M["trim"])
    # --- engine cylinder slung under the forward body, glowing front, ringed, with a pylon
    EY, EZ, ER = 2.22, -0.56, 0.18
    cyl(f"PodEngine_{sy}", (-3.35, Y(EY), EZ), ER, 1.0, M["hull_dark"], verts=20)
    for i, x in enumerate((-3.1, -3.45, -3.8)):
        cyl(f"PodEngineRing_{i}_{sy}", (x, Y(EY), EZ), ER + 0.025, 0.07, M["trim"], verts=20)
    cyl(f"PodEngineGlow_{sy}", (-2.84, Y(EY), EZ), ER * 0.82, 0.02, M["engine"], verts=20)
    cyl(f"PodEngineLip_{sy}", (-2.87, Y(EY), EZ), ER + 0.01, 0.06, M["trim"], verts=20, r2=ER * 0.85, cap=False)
    # r11: plain cone cap replaced by the faceted end cap below
    loft(f"PodEnginePylon_{sy}", [[(x, Y(EY - 0.1), EZ + 0.1), (x, Y(EY + 0.1), EZ + 0.1), (x, Y(EY + 0.12), -0.25), (x, Y(EY - 0.12), -0.25)]
                                  for x in (-3.0, -3.8)], M["hull_dark"], bevel=0.01)

FIN_PTS, STRAKE_PTS = {}, {}
# =================================================================== AFT SECTION (r8: free redesign -- sci-fi shuttle tail)
# Replaces the r7 stepped roof boxes, ringed cone, rear fairing and twin belly nozzles.  The reference doesn't show the rear,
# so this is designed: a sculpted, tapering armoured aft hull ending in a framed engine cowl with two bell main engines and
# an upper rectangular impulse slot, wing-root thrusters on the wings' trailing faces, dorsal spine, roof/side heat vents,
# a ventral rear ramp and twin canted ventral strakes.
def aft_ring(x, hw, zb, zt):
    h = zt - zb
    pts = [(0.62, zb), (0.92, zb + 0.12 * h), (1.0, zb + 0.3 * h), (1.0, zb + 0.62 * h), (0.86, zb + 0.84 * h), (0.55, zt)]
    return [(x, hw * py, pz) for py, pz in pts] + [(x, -hw * py, pz) for py, pz in reversed(pts)]
AFT = [(-3.6, 1.22, -0.95, 1.98), (-4.5, 1.18, -0.88, 1.86), (-5.4, 1.13, -0.74, 1.64), (-6.2, 1.08, -0.62, 1.42), (-6.4, 1.06, -0.6, 1.38)]
aft_hw = lambda x: interp(AFT, x, 1); aft_zb = lambda x: interp(AFT, x, 2); aft_zt = lambda x: interp(AFT, x, 3)
loft("AftHull", [aft_ring(*r_) for r_ in AFT], M["hull"], bevel=0.012, smooth_angle=30)
# armour belt where the aft hull meets the cowl
loft("AftBelt", [aft_ring(x, hw + d, zb - d, zt + d) for x, hw, zb, zt, d in [(-6.0, 1.09, -0.65, 1.46, 0.0), (-6.04, 1.09, -0.65, 1.46, 0.025),
                                                                              (-6.16, 1.08, -0.63, 1.43, 0.025), (-6.2, 1.08, -0.63, 1.43, 0.0)]], M["hull_dark"])
# --- r9 engine housing: an armour collar proud of the hull end, then faceted plates tapering inward to a smaller back
# face, from which two octagonal nozzle shrouds emerge around the bells (housing narrows into the nozzles, no square box)
def ring_part(x, hw, zb, zt, idx, sy, grow=0.0):
    r_ = aft_ring(x, hw, zb, zt); half = r_[:6] if sy > 0 else r_[6:][::-1]
    cy, cz = 0.0, (zb + zt) / 2
    return [(px, py + (py - cy) * grow, pz + (pz - cz) * grow) for px, py, pz in (half[i] for i in idx)]
HOUS = [(-6.22, 1.08, -0.63, 1.43), (-6.25, 1.115, -0.66, 1.455), (-6.48, 1.115, -0.66, 1.455), (-6.52, 1.09, -0.635, 1.43),
        (-6.82, 0.95, -0.5, 1.27), (-6.86, 0.9, -0.46, 1.23)]
loft("EngineHousing", [aft_ring(*h_) for h_ in HOUS], M["hull_dark"], bevel=0.012, smooth_angle=25)
CXB = -6.86
loft("EngineBackFace", [aft_ring(CXB + 0.005, 0.86, -0.43, 1.2), aft_ring(CXB - 0.015, 0.86, -0.43, 1.2)], M["trim"])
for sy in (1, -1):
    # chamfered armour plates on the tapering faces (upper chamfer, side, lower chamfer), slightly proud
    for nm, idx in (("Up", (3, 4, 5)), ("Side", (2, 3)), ("Low", (0, 1))):
        loft(f"HousingPlate{nm}_{sy}", [ring_part(x_, *p_, idx, sy, 0.03) + ring_part(x_, *p_, idx, sy, -0.005)[::-1]
                                        for x_, p_ in ((-6.56, (1.07, -0.615, 1.41)), (-6.79, (0.96, -0.51, 1.28)))], M["hull"], bevel=0.006)
# main engines: two bells in faceted octagonal shrouds
def oct_r(x, cy, cz, r, n=8): return [(x, cy + r * math.cos(a_), cz + r * math.sin(a_)) for a_ in [k * 2 * math.pi / n + math.pi / n for k in range(n)]]
for sy in (1, -1):
    ny, nz = sy * 0.46, 0.2
    loft(f"NozzleShroud_{sy}", [oct_r(-6.8, ny, nz, 0.5), oct_r(-6.98, ny, nz, 0.5), oct_r(-7.06, ny, nz, 0.46), oct_r(-7.06, ny, nz, 0.43), oct_r(-6.9, ny, nz, 0.43)],
         M["hull_dark"], cap=False, bevel=0.008, smooth_angle=25)
    loft(f"NozzleShroudBand_{sy}", [oct_r(-6.9, ny, nz, 0.5), oct_r(-6.91, ny, nz, 0.52), oct_r(-6.95, ny, nz, 0.52), oct_r(-6.96, ny, nz, 0.5)], M["trim"], cap=False)
    cyl(f"MainBell_{sy}", (-7.0, ny, nz), 0.4, 0.7, M["gun"], verts=28, r2=0.26, cap=False)
    cyl(f"MainBellOuter_{sy}", (-6.99, ny, nz), 0.425, 0.66, M["hull_dark"], verts=28, r2=0.29, cap=False)
    loft(f"MainBellRim_{sy}", [[(x, ny + r * math.cos(a_), nz + r * math.sin(a_)) for a_ in [k * 2 * math.pi / 28 for k in range(28)]]
                               for x, r in ((-7.32, 0.395), (-7.32, 0.44), (-7.36, 0.44), (-7.36, 0.395))], M["trim"], cap=False)   # r11: closed washer rim
    for i, x in enumerate((-7.13, -7.24)):
        cyl(f"MainBellBand_{i}_{sy}", (x, ny, nz), 0.26 + (0.14 * (-6.65 - x) / 0.7) + 0.035, 0.03, M["trim"], verts=28, cap=False)
    cyl(f"MainGlow_{sy}", (-6.9, ny, nz), 0.25, 0.02, M["engine_aft"], verts=28)
    cyl(f"MainGlowCore_{sy}", (-6.96, ny, nz), 0.06, 0.1, M["engine"], verts=16, r2=0.12)
    for k in range(6):   # turbine spokes in the throat
        a_ = k * math.pi / 3
        box(f"MainSpoke_{k}_{sy}", (-6.93, ny + 0.11 * math.cos(a_), nz + 0.11 * math.sin(a_)), (0.03, 0.03, 0.22), M["trim"], rot=(a_ + math.pi / 2, 0, 0))
# impulse slot on the back face above the bells: chamfered frame, dark recess, thin glowing slit, two horizontal vanes
side_prism("ImpulseFrameTop", [(CXB, 1.12), (CXB - 0.16, 1.09), (CXB - 0.16, 1.04), (CXB, 1.02)], -0.62, 0.62, M["hull_dark"], bevel=0.008)
side_prism("ImpulseFrameBot", [(CXB, 0.84), (CXB - 0.16, 0.82), (CXB - 0.16, 0.77), (CXB, 0.74)], -0.62, 0.62, M["hull_dark"], bevel=0.008)
box("ImpulseRecess", (CXB - 0.02, 0, 0.93), (0.02, 1.24, 0.36), M["trim"])
box("ImpulseGlow", (CXB - 0.035, 0, 0.93), (0.01, 1.14, 0.12), M["engine_aft"])
for z in (0.895, 0.965):
    box(f"ImpulseVane_{z}", (CXB - 0.1, 0, z), (0.14, 1.18, 0.012), M["trim"])
for sy in (1, -1):
    prism(f"ImpulseCap_{sy}", [(CXB, sy * 0.6, 0.72), (CXB, sy * 0.6, 1.14), (CXB - 0.16, sy * 0.62, 1.1), (CXB - 0.16, sy * 0.62, 0.76)], (0, sy * 0.05, 0), M["hull_dark"], bevel=0.006)
# dorsal spine: low armoured ridge on the aft roof with a lamp
side_prism("DorsalSpine", [(-4.4, aft_zt(-4.4) - 0.05), (-4.9, aft_zt(-4.9) + 0.2), (-6.1, aft_zt(-6.1) + 0.24), (-6.55, aft_zt(-6.4) + 0.12),
                           (-6.62, aft_zt(-6.4) - 0.1), (-6.2, aft_zt(-6.2) - 0.08)], -0.12, 0.12, M["hull_dark"], bevel=0.015)
box("DorsalLamp", (-5.5, 0, aft_zt(-5.5) + 0.235), (0.35, 0.05, 0.03), M["glow"])
for sy in (1, -1):
    Y = lambda y: sy * y
    # roof heat vents beside the spine (recessed panel + slats)
    for x0, x1 in [(-4.75, -5.95)]:
        n = 7
        loft(f"RoofVentPanel_{sy}", [[(x, Y(0.2), aft_zt(x) + 0.005), (x, Y(0.52), aft_zt(x) + 0.005), (x, Y(0.52), aft_zt(x) + 0.03), (x, Y(0.2), aft_zt(x) + 0.03)]
                                      for x in (x0, x1)], M["trim"])
        for k in range(n):
            x = lerp(x0 - 0.08, x1 + 0.08, k / (n - 1))
            box(f"RoofVentSlat_{k}_{sy}", (x, Y(0.36), aft_zt(x) + 0.055), (0.04, 0.3, 0.05), M["hull_dark"], rot=(0, -0.35, 0))
    # side heat vents on the exposed aft flank behind the wing
    hx = lambda x: aft_hw(x) + 0.005
    loft(f"SideVentPanel_{sy}", [[(x, Y(hx(x)), -0.22), (x, Y(hx(x)), 0.5), (x, Y(hx(x) + 0.03), 0.5), (x, Y(hx(x) + 0.03), -0.22)] for x in (-5.72, -6.0)],
         M["trim"])
    for k in range(5):
        z = lerp(-0.15, 0.43, k / 4)
        box(f"SideVentSlat_{k}_{sy}", (-5.86, Y(hx(-5.86) + 0.04), z), (0.26, 0.04, 0.05), M["hull_dark"], rot=(-0.5 * sy, 0, 0))
    box(f"AftFlankLamp_{sy}", (-6.125, Y(aft_hw(-6.15) + 0.015), 0.62), (0.07, 0.02, 0.2), M["glow"])   # r12b diag: fits the 15 cm belt (overhung it)
    # r11: wing-root thruster rebuilt with structure (see "wing-root hump rebuilt" below)
    # r13: the old cowl/wing-tip RCS clusters were removed; the 9-pod cold-gas RCS layout is built after the surface helpers
    # twin canted ventral strakes under the engine
    pts = []
    for x, d in [(-5.0, 0.0), (-6.45, 0.0), (-7.1, 0.92), (-6.05, 1.0)]:   # r10: 2x size, same cant; top edge sunk into the belly
        pts.append((x, sy * (0.72 + d * 0.45), aft_zb(min(x, -3.6)) - d + 0.08))
    prism(f"VentralStrake_{sy}", pts, (0, sy * 0.1, 0), M["hull_dark"], bevel=0.012); STRAKE_PTS[sy] = pts
    box(f"StrakeLamp_{sy}", (-6.7, sy * (0.72 + 0.72 * 0.45 + 0.11), aft_zb(-6.4) - 0.62), (0.24, 0.02, 0.04), M["glow"], rot=(sy * 0.42, 0, 0))
    # twin canted dorsal tail fins on the aft roof edges (r10: 2x size, same placement and cant; root sunk into the roof/housing)
    rt = lambda x: aft_zt(x) if x >= -6.4 else interp([(-6.4, 1.38), (-6.52, 1.38), (-6.82, 1.26), (-7.0, 1.26)], x, 1)
    fp = []
    for x, h in [(-5.0, 0.0), (-6.62, 0.0), (-7.15, 1.24), (-6.25, 1.32)]:
        fp.append((x, sy * (0.6 + h * 0.6), rt(x) - 0.08 + h))
    prism(f"TailFin_{sy}", fp, (0, sy * 0.14, 0), M["hull_dark"], bevel=0.012); FIN_PTS[sy] = fp
    # r12b diag P14/15: lamp laid flat on the fin's outer face (it stood across the top edge and the fin plane sliced it diagonally)
    _h = 1.16; _x = -6.75; _n = Vector((0, sy * 0.857, -0.514))
    _z = _n.normalized(); _xa = Vector((1, 0, 0)) - _z * _z.x; _xa.normalize(); _ya = _z.cross(_xa)
    _lamp = box(f"TailFinLamp_{sy}", (0, 0, 0.0), (0.3, 0.04, 0.02), M["glow"])
    _lamp.matrix_world = Matrix.Translation(Vector((_x, sy * (0.6 + 0.6 * _h + 0.14), rt(_x) - 0.08 + _h))) @ Matrix((_xa, _ya, _z)).transposed().to_4x4() @ _lamp.matrix_world
    loft(f"TailFinRoot_{sy}", [[(x, sy * 0.52, rt(x) - 0.03), (x, sy * 0.86, rt(x) - 0.06), (x, sy * 0.8, rt(x) + 0.1), (x, sy * 0.56, rt(x) + 0.12)]
                               for x in (-5.2, -6.6)], M["hull"], bevel=0.008)
# ventral rear ramp: recessed panel with hinge bar and side rails
loft("RearRamp", [[(x, 0.55, aft_zb(x) - 0.005), (x, 0.55, aft_zb(x) - 0.035), (x, -0.55, aft_zb(x) - 0.035), (x, -0.55, aft_zb(x) - 0.005)] for x in (-4.9, -6.3)],
     M["hull_dark"], bevel=0.005)
box("RampHinge", (-4.95, 0, aft_zb(-4.95) - 0.05), (0.08, 1.0, 0.04), M["trim"])
for sy in (1, -1):
    loft(f"RampRail_{sy}", [[(x, sy * 0.58, aft_zb(x) - 0.0), (x, sy * 0.62, aft_zb(x) - 0.0), (x, sy * 0.62, aft_zb(x) - 0.06), (x, sy * 0.58, aft_zb(x) - 0.06)]
                            for x in (-4.9, -6.3)], M["trim"])
box("RampLamp", (-6.2, 0, aft_zb(-6.2) - 0.045), (0.05, 0.6, 0.02), M["glow"])

# =================================================================== hull / cabin light strips
for sy in (1, -1):
    for i, (x, f, L) in enumerate([(3.6, 0.52, 0.7), (1.4, 0.52, 0.9), (-0.7, 0.52, 0.7), (2.5, 0.15, 0.5), (-1.4, 0.15, 0.6)]):
        yo = interp(SPON, x, 2); zb = interp(SPON, x, 3); zt = interp(SPON, x, 4)
        if f < 0.3:   # r11: low strips seated on the sponson's lower slope (they floated before)
            yi = interp(SPON, x, 1); w = yo - yi; h = zt - zb
            p0 = (yi + w * 0.5, zb); p1 = (yo - w * 0.12, zb + h * 0.2); t_ = f / 0.2
            ys, zs = lerp(p0[0], p1[0], t_), lerp(p0[1], p1[1], t_)
            ny_, nz_ = (p1[1] - p0[1]), -(p1[0] - p0[0]); nl = math.hypot(ny_, nz_); ny_, nz_ = ny_ / nl, nz_ / nl
            box(f"HullStrip_{i}_{sy}", (x, sy * (ys + ny_ * 0.008), zs + nz_ * 0.008), (L, 0.03, 0.045), M["glow"], rot=(-sy * math.atan2(-nz_, ny_), 0, 0))
        else:
            box(f"HullStrip_{i}_{sy}", (x, sy * (yo + 0.06), zb + (zt - zb) * f), (L, 0.03, 0.045), M["glow"])
    for i, x in enumerate((4.0, 2.6, 0.9, -2.6)):
        y, _ = wall_y(x, deck(x) + 0.05)
        box(f"ShellLamp_{i}_{sy}", (x, sy * (y + 0.01), deck(x) + 0.08), (0.2, 0.03, 0.04), M["glow"])

# belly: keel plate + layered panels so the underside isn't a blank blob
loft("BellyKeel", [[(x, sy_ * w, zb_at(x) + dz) for sy_, w, dz in [(1, 0.32, 0.02), (1, 0.26, -0.07), (-1, 0.26, -0.07), (-1, 0.32, 0.02)]]
                   for x in (4.4, 3.0, 1.45)], M["hull_dark"], bevel=0.01)
loft("BellyKeelAft", [[(x, sy_ * w, zb_at(x) + dz) for sy_, w, dz in [(1, 0.32, 0.02), (1, 0.26, -0.07), (-1, 0.26, -0.07), (-1, 0.32, 0.02)]]
                   for x in (-1.6, -3.0, -4.6)], M["hull_dark"], bevel=0.01)   # r11: keel split for the boarding ramp
for sy in (1, -1):
    for i, (x0, x1) in enumerate([(4.2, 2.6), (2.4, 0.5), (0.3, -1.6), (-1.8, -3.8)]):
        _xs = [x0 + (x1 - x0) * k / 6 for k in range(7)]   # r12b diag P05/P06: 7 stations so the panel follows the belly curve
        rings = [[(x, sy * w, zb_at(x) + dz) for w, dz in [(0.42, 0.01), (0.42, -0.035), (0.6 * hw_at(x) - 0.02, -0.035), (0.6 * hw_at(x) - 0.02, 0.01)]] for x in _xs]
        loft(f"BellyPanel_{i}_{sy}", rings, M["hull"] if i % 2 else M["hull_dark"], bevel=0.006)
    for x in (3.4, 0.0, -3.2):
        box(f"BellyLamp_{x}_{sy}", (x, sy * 0.9 * hw_at(x), zb_at(x) + 0.12), (0.35, 0.03, 0.04), M["glow"])

# =================================================================== r11 helpers: surface seating (ray casts onto the built hull)
from mathutils import Matrix as _Mx
def surf_hit(origin, direction, skip=()):
    origin = Vector(origin); direction = Vector(direction).normalized(); best = None
    for o in ROOT.children:
        if o.type != "MESH" or o.name.startswith(skip): continue
        ok, loc, nrm, _ = o.ray_cast(origin, direction, distance=20.0)
        if ok and (best is None or (loc - origin).length < (best[0] - origin).length): best = (loc.copy(), nrm.copy())
    if best is None: raise RuntimeError(f"no surface hit from {tuple(origin)}")
    loc, nrm = best
    if nrm.dot(direction) > 0: nrm = -nrm
    return loc, nrm
def frame_at(loc, nrm, fwd):
    z = Vector(nrm).normalized(); x = Vector(fwd) - z * Vector(fwd).dot(z); x.normalize(); y = z.cross(x)
    return _Mx.Translation(loc) @ _Mx((x, y, z)).transposed().to_4x4()
def placed(ob, Mw):
    ob.matrix_world = Mw @ ob.matrix_world; return ob
RCS_LOG = []
def rcs_quad(name, origin, ray, fwd, size, nozzles, sink=0.015):
    """r13 cold-gas RCS pod: one bevelled block housing seated on the surface hit by a ray (sunk `sink`), plus 2-4 small conical
    nozzle bells, each leaving the housing face whose axis best matches the requested WORLD thrust-exhaust direction."""
    loc, n = surf_hit(origin, ray, skip=("cut", "RCS")); Mw = frame_at(loc, n, fwd); R = Mw.to_3x3()
    sx, sw, h = size; c0 = Vector((0, 0, h / 2 - sink))
    placed(box(name, tuple(c0), (sx, sw, h), M["hull_dark"], bevel=0.012), Mw)
    L, r_in, r_out = 0.07, 0.022, 0.04
    out = []
    for k, d in enumerate(nozzles):
        dl = R.transposed() @ Vector(d); ax = max(range(3), key=lambda i: abs(dl[i])); sg = 1 if dl[ax] > 0 else -1
        e = Vector((0, 0, 0)); e[ax] = sg
        c = c0 + e * ((sx, sw, h)[ax] / 2 - 0.008 + L / 2)
        r1, r2 = (r_in, r_out) if sg * (-1 if ax == 1 else 1) > 0 else (r_out, r_in)   # cyl(): r2 end is +X / -Y / +Z
        placed(cyl(f"{name}_Nozzle{k}", tuple(c), r1, L, M["gun"], axis="XYZ"[ax], verts=10, r2=r2, cap=False), Mw)
        out.append(tuple(round(v, 2) for v in (R @ e)))
    RCS_LOG.append((name, tuple(round(v, 2) for v in loc), tuple(round(v, 2) for v in n), out))
CREASE_X = (-5.0,)   # r12: known host creases (x) on the rear shoulder; plate grids put a column exactly on them
def _breaks(a, b, step, cuts=()):
    pts = [0.0] + sorted((c - a) / (b - a) for c in cuts if min(a, b) + 0.01 < c < max(a, b) - 0.01) + [1.0]
    out = [0.0]
    for p0, p1 in zip(pts, pts[1:]):
        k = max(1, math.ceil(abs(p1 - p0) * abs(b - a) / step)); out += [p0 + (p1 - p0) * i / k for i in range(1, k + 1)]
    return out
def surf_plate(name, corners, mat, thick=0.03, down=(0, 0, -1), nu=4, nv=3, lift=0.0, skip=(), step=0.05, sink=0.006):
    """plate conforming to the surface below a quad of (x,y,z_start) corners (ray cast along `down`), thickness along the normal.
    r12: dense grid (~5 cm) with grid lines placed exactly on known host creases, so the plate bends on the crease instead of
    bridging it (host poking through) or folding over it (ragged slivers)."""
    C = [Vector(c) for c in corners]; d = Vector(down)
    lu = max((C[1] - C[0]).length, (C[2] - C[3]).length); lv = max((C[3] - C[0]).length, (C[2] - C[1]).length)
    us = _breaks(C[0].x, C[1].x, step, CREASE_X) if abs(C[1].x - C[0].x) > 1e-6 and abs(C[2].x - C[3].x - (C[1].x - C[0].x)) < 1e-6 and abs(C[3].x - C[0].x) < 1e-6 else [i / max(nu, math.ceil(lu / step)) for i in range(max(nu, math.ceil(lu / step)) + 1)]
    vs = [j / max(nv, math.ceil(lv / step)) for j in range(max(nv, math.ceil(lv / step)) + 1)]
    nu, nv = len(us) - 1, len(vs) - 1
    grid = []
    for v in vs:
        row = []
        for u in us:
            p = C[0].lerp(C[1], u).lerp(C[3].lerp(C[2], u), v)
            loc, n = surf_hit(p, d, skip=skip); row.append((loc, n))
        grid.append(row)
    bm = bmesh.new()
    # r12: thickness along a neighbourhood-smoothed normal (raw per-hit normals fold the top over concave creases -> ragged slivers)
    def _sn(j, i, r=3):
        acc = Vector()
        for jj in range(max(0, j - r), min(nv, j + r) + 1):
            for ii in range(max(0, i - r), min(nu, i + r) + 1): acc += grid[jj][ii][1]
        return acc.normalized()
    SN = [[_sn(j, i) for i in range(nu + 1)] for j in range(nv + 1)]
    top = [[bm.verts.new(grid[j][i][0] + SN[j][i] * (thick + lift)) for i in range(nu + 1)] for j in range(nv + 1)]
    bot = [[bm.verts.new(grid[j][i][0] - SN[j][i] * sink) for i in range(nu + 1)] for j in range(nv + 1)]
    for j in range(nv):
        for i in range(nu):
            bm.faces.new((top[j][i], top[j][i + 1], top[j + 1][i + 1], top[j + 1][i]))
            bm.faces.new((bot[j][i], bot[j + 1][i], bot[j + 1][i + 1], bot[j][i + 1]))
    ring_t = [top[0][i] for i in range(nu + 1)] + [top[j][nu] for j in range(1, nv + 1)] + [top[nv][i] for i in range(nu - 1, -1, -1)] + [top[j][0] for j in range(nv - 1, 0, -1)]
    ring_b = [bot[0][i] for i in range(nu + 1)] + [bot[j][nu] for j in range(1, nv + 1)] + [bot[nv][i] for i in range(nu - 1, -1, -1)] + [bot[j][0] for j in range(nv - 1, 0, -1)]
    for k in range(len(ring_t)):
        k2 = (k + 1) % len(ring_t); bm.faces.new((ring_t[k], ring_b[k], ring_b[k2], ring_t[k2]))
    return finish(bm, name, mat, bevel=0.006, smooth_angle=20)
def nav_light(name, a, b, t, plane_n, centroid, lens_mat, size=0.16, across=0.2):
    a, b = Vector(a), Vector(b); e = (b - a).normalized(); m = a.lerp(b, t)
    pn = Vector(plane_n).normalized(); out = pn.cross(e)
    if out.dot(m - Vector(centroid)) < 0: out = -out
    Mw = _Mx.Translation(m) @ _Mx((e, pn, out)).transposed().to_4x4()   # local X along edge, Y across fin, Z outward
    placed(box(name + "_Housing", (0, 0, 0.0), (size, across, 0.08), M["trim"], bevel=0.008), Mw)
    placed(box(name + "_Lens", (0, 0, 0.045), (size * 0.78, across * 0.7, 0.035), lens_mat, bevel=0.006), Mw)

# =================================================================== r13: cold-gas RCS, 9 pods at the extremities (replaces all 14 r8/r11 clusters)
# Layout (max lever arm about the CoM ~(-0.4, 0, 0.3)): 2 nose-flank (fore-most outboard point, sponson belt), 2 wing-tip faces
# (outermost, 5 m span arm -> roll), 2 aft-corner (rear housing quarters, aft-most outboard), 1 dorsal-aft centre (top-aft extreme),
# 1 ventral-fwd centre (keel, lowest fwd point), 1 chin centre (fore-most low point). Nozzle lists are exhaust directions.
X_, Y_, Z_ = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
for sy in (1, -1):
    rcs_quad(f"RCS_NoseFlank_{sy}", (4.72, sy * 3.0, -0.455), (0, -sy, 0), (1, 0, 0), (0.26, 0.17, 0.13), (X_, sy * Y_, Z_, -Z_))
    rcs_quad(f"RCS_WingTip_{sy}", (-4.95, sy * 6.0, 0.39), (0, -sy, 0), (1, 0, 0), (0.26, 0.26, 0.13), (sy * Y_, Z_, -Z_, -X_))
    rcs_quad(f"RCS_AftQuarter_{sy}", (-6.68, sy * 3.0, 0.40), (0, -sy, 0), (1, 0, 0), (0.24, 0.24, 0.13), (-X_, sy * Y_, Z_, -Z_))
rcs_quad("RCS_DorsalAft", (-6.33, 0, 4.0), (0, 0, -1), (1, 0, 0), (0.24, 0.24, 0.13), (Z_, Y_, -Y_))
rcs_quad("RCS_VentralFwd", (2.6, 0, -4.0), (0, 0, 1), (1, 0, 0), (0.26, 0.26, 0.13), (-Z_, Y_, -Y_))
rcs_quad("RCS_Chin", (5.45, 0, -4.0), (0, 0, 1), (1, 0, 0), (0.24, 0.24, 0.12), (-Z_, X_))
for r_ in RCS_LOG: print("RCSPOD", r_)

# =================================================================== r12: navigation lights per aviation/maritime convention
# red sidelight at the port-most extent (port wing-tip block, forward-outboard corner), green mirrored on starboard: lenses face
# outboard + forward only, the tip block and the whole ship shield them from the opposite side.  White stern light on a short
# boom at the aft-most centreline, lens facing aft inside a hood (invisible from the sides/front).  Optional white anti-collision
# strobe on top, recessed inside a rim so it only reads from above.
for sy in (1, -1):
    Y = lambda y: sy * y
    col = M["nav_red"] if sy > 0 else M["nav_green"]
    nm_ = "Port" if sy > 0 else "Stbd"
    z0, z1 = 0.335, 0.485
    hous = [(-4.42, Y(4.962)), (-4.42, Y(5.045)), (-4.165, Y(5.045)), (-4.092, Y(4.99)), (-4.092, Y(4.962))]
    prism(f"Nav{nm_}_Housing", [(x, y, z0) for x, y in hous], (0, 0, z1 - z0), M["trim"], bevel=0.006)
    lens = [(-4.39, Y(5.03)), (-4.39, Y(5.058)), (-4.158, Y(5.058)), (-4.079, Y(4.998)), (-4.089, Y(4.984)), (-4.166, Y(5.03))]
    prism(f"Nav{nm_}_Lens", [(x, y, z0 + 0.03) for x, y in lens], (0, 0, z1 - z0 - 0.06), col, bevel=0.004)
    for k_, zz in enumerate((z1 - 0.006, z0 - 0.016)):   # visor lips above/below the lens (hard-edged cut-off)
        lip = [(-4.43, Y(5.0)), (-4.43, Y(5.075)), (-4.15, Y(5.075)), (-4.06, Y(5.005)), (-4.075, Y(4.98)), (-4.1, Y(4.98))]
        prism(f"Nav{nm_}_Visor_{k_}", [(x, y, zz) for x, y in lip], (0, 0, 0.022), M["hull_dark"], bevel=0.003)
# stern light: short faceted boom off the upper engine-housing back, centreline, lens recessed in a hood facing straight aft
box("NavStern_Boom", (-6.98, 0, 1.245), (0.5, 0.22, 0.1), M["hull_dark"], bevel=0.01)
box("NavStern_Lens", (-7.232, 0, 1.245), (0.02, 0.17, 0.066), M["nav_white"])
for k_, (c_, s_) in enumerate((((-7.247, 0, 1.301), (0.05, 0.24, 0.014)), ((-7.247, 0, 1.189), (0.05, 0.24, 0.014)),
                               ((-7.247, 0.113, 1.245), (0.05, 0.014, 0.11)), ((-7.247, -0.113, 1.245), (0.05, 0.014, 0.11)))):
    box(f"NavStern_Hood_{k_}", c_, s_, M["trim"], bevel=0.003)
# top anti-collision strobe: recessed white lens inside a raised octagonal rim on the aft roof centreline
_zs = [surf_hit((-3.4 + 0.11 * math.cos(a_), 0.11 * math.sin(a_), 5), (0, 0, -1))[0].z for a_ in [k * math.pi / 4 for k in range(8)]] + [surf_hit((-3.4, 0, 5), (0, 0, -1))[0].z]
zt = max(_zs); zb_ = min(_zs)
def _oct(r, z): return [(-3.4 + r * math.cos(math.pi / 8 + k * math.pi / 4), r * math.sin(math.pi / 8 + k * math.pi / 4), z) for k in range(8)]
loft("NavStrobe_Base", [_oct(0.11, zb_ - 0.01), _oct(0.11, zt + 0.015), _oct(0.095, zt + 0.025)], M["trim"], bevel=0.003)
loft("NavStrobe_Rim", [_oct(0.085, zt + 0.02), _oct(0.085, zt + 0.07), _oct(0.07, zt + 0.07), _oct(0.07, zt + 0.02)], M["hull_dark"], cap=True)
loft("NavStrobe_Lens", [_oct(0.066, zt + 0.018), _oct(0.066, zt + 0.045)], M["nav_white"])

# =================================================================== r11: wing-root hump rebuilt with structure (replaces the plain box thruster)
for sy in (1, -1):
    Y = lambda y: sy * y
    yc, zc, hy, hz = 1.72, 0.6, 0.46, 0.22
    def oct_rect(x, hy_, hz_, c=0.06):
        pts = [(hy_, hz_ - c), (hy_ - c, hz_), (-hy_ + c, hz_), (-hy_, hz_ - c), (-hy_, -hz_ + c), (-hy_ + c, -hz_), (hy_ - c, -hz_), (hy_, -hz_ + c)]
        return [(x, Y(yc + py), zc + pz) for py, pz in pts]
    # hollow chamfered nozzle housing: tapered outer skin, chamfered lip, deep inner walls
    loft(f"RootNozzle_{sy}", [oct_rect(-5.56, hy + 0.05, hz + 0.05, 0.08), oct_rect(-5.8, hy, hz), oct_rect(-5.86, hy - 0.03, hz - 0.03),
                              oct_rect(-5.86, hy - 0.06, hz - 0.06, 0.04), oct_rect(-5.66, hy - 0.06, hz - 0.06, 0.04)], M["hull_dark"], cap=False, smooth_angle=20)
    loft(f"RootNozzleBack_{sy}", [oct_rect(-5.655, hy - 0.055, hz - 0.055, 0.04), oct_rect(-5.675, hy - 0.055, hz - 0.055, 0.04)], M["trim"])
    box(f"RootNozzleGlow_{sy}", (-5.68, Y(yc), zc), (0.01, 2 * (hy - 0.1), 0.07), M["engine_aft"])
    for k_, dy in enumerate((-0.2, 0.0, 0.2)):
        box(f"RootNozzleRib_{k_}_{sy}", (-5.76, Y(yc + dy), zc), (0.18, 0.025, 2 * (hz - 0.06)), M["trim"])
    for k_, dz in enumerate((-0.1, -0.05, 0.05, 0.1)):
        box(f"RootNozzleVane_{k_}_{sy}", (-5.76, Y(yc), zc + dz), (0.18, 2 * (hy - 0.06), 0.014), M["trim"])
    # armoured hood stepping out over the housing, with an angled front chamfer
    side_prism(f"RootHood_{sy}", [(-5.5, zc + hz + 0.04), (-5.95, zc + hz + 0.04), (-5.98, zc + hz + 0.09), (-5.5, zc + hz + 0.16)],
               Y(yc - hy - 0.08), Y(yc + hy + 0.08), M["hull"], bevel=0.008)
    # side gusset brackets tying the housing into the trailing face
    for k_, yy in enumerate((yc - hy - 0.06, yc + hy + 0.03)):
        side_prism(f"RootGusset_{k_}_{sy}", [(-5.5, zc - hz), (-5.5, zc + hz + 0.05), (-5.84, zc + hz + 0.05), (-5.7, zc - hz)], Y(yy), Y(yy + 0.04), M["hull_dark"], bevel=0.005)
    # recessed vent grille below the housing
    loft(f"RootVent_{sy}", [[(x, Y(y), z) for y, z in ((1.62, 0.15), (1.62, 0.33), (2.2, 0.33), (2.2, 0.15))] for x in (-5.55, -5.63)], M["trim"])
    for k_ in range(5):
        y = lerp(1.68, 2.14, k_ / 4)
        box(f"RootVentRib_{k_}_{sy}", (-5.64, Y(y), 0.24), (0.05, 0.025, 0.17), M["hull_dark"], rot=(0, 0, sy * 0.4))
    # stepped plate on the trailing face above the hood
    side_prism(f"RootStepPlate_{sy}", [(-5.55, zc + hz + 0.17), (-5.66, zc + hz + 0.17), (-5.66, zc + hz + 0.27), (-5.55, zc + hz + 0.3)],
               Y(1.28), Y(2.2), M["hull_dark"], bevel=0.006)
    # under-pod integration: faceted fairing over the pod top, faceted pylon, armoured rear end cap
    def pod_arc(x, r, zlift=0.0):
        return [(x, Y(EY + r * math.cos(a_)), EZ + zlift + r * math.sin(a_)) for a_ in [math.radians(d) for d in (-10, 30, 70, 110, 150, 190)]] + \
               [(x, Y(EY - r * 0.9), -0.18), (x, Y(EY + r * 0.9), -0.18)]
    loft(f"PodFairing_{sy}", [pod_arc(-2.98, 0.2), pod_arc(-3.05, 0.235), pod_arc(-3.75, 0.235), pod_arc(-3.86, 0.205)], M["hull"], bevel=0.006, smooth_angle=20)
    loft(f"PodEndCap_{sy}", [oct_r(x, Y(EY), EZ, r) for x, r in ((-3.84, 0.19), (-3.92, 0.19), (-3.98, 0.15), (-4.0, 0.1))], M["hull_dark"], bevel=0.005, smooth_angle=20)
    cyl(f"PodEndGlow_{sy}", (-4.0, Y(EY), EZ), 0.06, 0.012, M["engine_aft"], verts=8)

# =================================================================== r11: rear shoulder structure (mark 1: plain area ahead of the dorsal fin root)
pass
for sy in (1, -1):
    Y = lambda y: sy * y
    surf_plate(f"ShoulderPlateA_{sy}", [(-3.75, Y(0.62), 4), (-4.55, Y(0.62), 4), (-4.55, Y(1.12), 4), (-3.75, Y(1.0), 4)], M["hull_dark"], 0.03)
    surf_plate(f"ShoulderPlateB_{sy}", [(-4.62, Y(0.92), 4), (-5.25, Y(0.92), 4), (-5.25, Y(1.2), 4), (-4.62, Y(1.16), 4)], M["hull"], 0.045)
    surf_plate(f"ShoulderVent_{sy}", [(-4.72, Y(0.93), 4), (-5.15, Y(0.93), 4), (-5.15, Y(1.12), 4), (-4.72, Y(1.1), 4)], M["trim"], 0.05)
    for k_ in range(5):   # ribs across the vent, seated by ray cast on the vent
        x = lerp(-4.78, -5.09, k_ / 4)
        loc, n = surf_hit((x, Y(1.02), 4), (0, 0, -1), skip=("ShoulderVentRib",))
        placed(box(f"ShoulderVentRib_{k_}_{sy}", (0, 0, 0.012), (0.035, 0.17, 0.03), M["hull_dark"], bevel=0.003), frame_at(loc, n, (1, 0, 0)))
    # fin-root fairing: faceted ramp from the shoulder plates up onto the fin root
    xs_ = (-4.6, -5.0, -5.3)
    rings = []
    for x, h in zip(xs_, (0.0, 0.09, 0.16)):
        zs_ = [surf_hit((x, Y(yy), 4), (0, 0, -1), skip=("ShoulderVentRib", "Shoulder"))[0].z for yy in (0.52, 0.86, 0.6, 0.69, 0.78)]
        za, zb = zs_[0] - 0.012, zs_[1] - 0.012   # r12: each bottom corner seated on the sloped shoulder
        zt_ = max(zs_) + 0.05 + h
        rings.append([(x, Y(0.52), za), (x, Y(0.86), zb), (x, Y(0.81), zt_), (x, Y(0.57), zt_)])
    loft(f"FinRootFairing_{sy}", rings, M["hull_dark"], bevel=0.006, smooth_angle=20)
    # big sloped wing-root top face: stepped armour plates, a ribbed vent and a raised crease strake
    # big sloped wing-root top: plates laid out on the host facets (crease at y~1.6 and y~1.95 become plate seams)
    surf_plate(f"ShoulderPlateC_{sy}", [(-3.9, Y(1.29), 4), (-4.6, Y(1.29), 4), (-4.6, Y(1.565), 4), (-3.9, Y(1.565), 4)], M["hull_dark"], 0.035)
    surf_plate(f"ShoulderPlateC2_{sy}", [(-3.97, Y(1.645), 4), (-4.6, Y(1.645), 4), (-4.6, Y(1.92), 4), (-4.03, Y(1.92), 4)], M["hull"], 0.03)
    surf_plate(f"ShoulderPlateD_{sy}", [(-4.68, Y(1.29), 4), (-5.45, Y(1.29), 4), (-5.45, Y(1.565), 4), (-4.68, Y(1.565), 4)], M["hull"], 0.03)
    surf_plate(f"ShoulderPlateD3_{sy}", [(-4.68, Y(1.645), 4), (-5.45, Y(1.645), 4), (-5.45, Y(1.92), 4), (-4.68, Y(1.92), 4)], M["hull_dark"], 0.03)
    surf_plate(f"ShoulderPlateD2_{sy}", [(-4.8, Y(1.34), 4), (-5.32, Y(1.34), 4), (-5.32, Y(1.52), 4), (-4.8, Y(1.52), 4)], M["hull_dark"], 0.06)
    surf_plate(f"ShoulderVent2_{sy}", [(-4.8, Y(1.69), 4), (-5.32, Y(1.69), 4), (-5.32, Y(1.88), 4), (-4.8, Y(1.88), 4)], M["trim"], 0.06)
    for k_ in range(6):
        x = lerp(-4.85, -5.27, k_ / 5)
        loc, n = surf_hit((x, Y(1.785), 4), (0, 0, -1), skip=("ShoulderVentRib",))
        placed(box(f"ShoulderVentRib2_{k_}_{sy}", (0, 0, 0.012), (0.03, 0.16, 0.03), M["hull_dark"], bevel=0.003), frame_at(loc, n, (1, 0, 0)))
    for k_, y in enumerate((1.24, 2.2)):   # raised seam strakes bounding the plate field
        surf_plate(f"ShoulderStrake_{k_}_{sy}", [(-3.9, Y(y - 0.025), 4), (-5.45, Y(y - 0.025), 4), (-5.45, Y(y + 0.025), 4), (-3.9, Y(y + 0.025), 4)], M["trim"], 0.05, nu=6, nv=1, step=0.04)
    # r12 (markup_plainside_r11): the big forward-facing sloped side face of the rear housing (wing leading chamfer) gets
    # layered armour: a framed access panel with bolts, a vent plate, a lower skirt plate, seam strip and brackets.
    SK = ("cut", "Plain")
    PX = -3.45; DX = (-1, 0, 0)
    # r13: inboard edge pulled in 1.07 -> 1.11/1.15; edge rays grazed the inboard wall and threw two spikes out of the plate edge
    surf_plate(f"PlainPlateA_{sy}", [(PX, Y(1.15), 1.06), (PX, Y(1.62), 1.08), (PX, Y(1.62), 1.21), (PX, Y(1.11), 1.48)], M["hull_dark"], 0.022, down=DX, skip=SK)
    # access panel frame (raised border strips) + recessed-looking inner hatch
    for k_, q in enumerate(([(1.27, 1.12), (1.57, 1.12), (1.57, 1.145), (1.27, 1.145)],
                            [(1.27, 1.395), (1.57, 1.235), (1.57, 1.26), (1.27, 1.42)],
                            [(1.27, 1.145), (1.295, 1.145), (1.295, 1.395), (1.27, 1.395)],
                            [(1.545, 1.145), (1.57, 1.145), (1.57, 1.248), (1.545, 1.248)])):
        surf_plate(f"PlainFrame_{k_}_{sy}", [(PX, Y(y_), z_) for y_, z_ in q], M["trim"], 0.028, down=DX, skip=("cut",), step=0.04, sink=0.008)
    surf_plate(f"PlainHatch_{sy}", [(PX, Y(1.31), 1.16), (PX, Y(1.53), 1.16), (PX, Y(1.53), 1.24), (PX, Y(1.31), 1.36)], M["hull"], 0.012, down=DX, skip=("cut",), step=0.04, sink=0.008)
    for k_, (y_, z_) in enumerate(((1.33, 1.18), (1.51, 1.18), (1.33, 1.33), (1.51, 1.235))):   # hatch bolts
        lo_, n_ = surf_hit((PX, Y(y_), z_), DX, skip=("cut",))
        placed(cyl(f"PlainBolt_{k_}_{sy}", (0, 0, 0.004), 0.012, 0.016, M["gun"], axis="Z", verts=6), frame_at(lo_, n_, (0, 0, 1)))
    # outboard plate with a louvred vent
    surf_plate(f"PlainPlateB_{sy}", [(PX, Y(1.67), 1.1), (PX, Y(2.02), 1.1), (PX, Y(2.02), 1.12), (PX, Y(1.67), 1.18)], M["hull"], 0.03, down=DX, skip=SK, step=0.03)
    surf_plate(f"PlainVent_{sy}", [(PX, Y(1.72), 1.105), (PX, Y(1.92), 1.105), (PX, Y(1.92), 1.127), (PX, Y(1.72), 1.162)], M["trim"], 0.02, down=DX, skip=("cut",), step=0.05, sink=0.008)
    for k_ in range(5):
        lo_, n_ = surf_hit((PX, Y(lerp(1.75, 1.89, k_ / 4)), 1.122), DX, skip=("cut",))
        placed(box(f"PlainVentRib_{k_}_{sy}", (0, 0, 0.012), (0.05, 0.018, 0.026), M["hull_dark"], bevel=0.003), frame_at(lo_, n_, (0, 0, 1)))
    # seam strip between the two plates and a pair of brackets on the upper edge
    surf_plate(f"PlainSeam_{sy}", [(PX, Y(1.63), 1.07), (PX, Y(1.66), 1.07), (PX, Y(1.66), 1.19), (PX, Y(1.63), 1.2)], M["hull_dark"], 0.04, down=DX, skip=SK, step=0.04, sink=0.01)
    # stepped upper armour plate along the top crease, bolted
    surf_plate(f"PlainStep_{sy}", [(PX, Y(1.07), 1.49), (PX, Y(1.40), 1.40), (PX, Y(1.40), 1.44), (PX, Y(1.07), 1.55)], M["hull"], 0.05, down=DX, skip=SK, step=0.03, sink=0.011)
    for k_ in range(3):
        y_ = lerp(1.11, 1.35, k_ / 2); z_ = lerp(1.515, 1.432, k_ / 2)
        lo_, n_ = surf_hit((PX, Y(y_), z_), DX, skip=("cut",))
        placed(cyl(f"PlainStepBolt_{k_}_{sy}", (0, 0, 0.004), 0.012, 0.016, M["gun"], axis="Z", verts=6), frame_at(lo_, n_, (0, 0, 1)))
    lo_, n_ = surf_hit((-4.2, Y(0.9), 4), (0, 0, -1)); placed(box(f"ShoulderLamp_{sy}", (0, 0, 0.012), (0.24, 0.035, 0.03), M["glow"]), frame_at(lo_, n_, (1, 0, 0)))

# =================================================================== r11: boarding ramp under the mid cabin (closed, flush; separate object hinged at its aft end)
RX0, RX1, RW = 1.3, -1.45, 0.33      # door front x, hinge x, half width
def belly_z(x): return zb_at(x)
xs_r = [RX0 + 0.08] + [x for x in (0.6,) if RX1 < x < RX0] + [RX1 - 0.08]
def rect_loop(x0, x1, w, dz, n=6):
    xs = [lerp(x0, x1, k / n) for k in range(n + 1)]
    return [(x, w, belly_z(x) + dz) for x in xs] + [(x, -w, belly_z(x) + dz) for x in reversed(xs)]
fr_o, fr_i = (RX0 + 0.08, RX1 - 0.08, RW + 0.07), (RX0 + 0.012, RX1 - 0.012, RW + 0.012)
loft("RampFrame", [rect_loop(*fr_o, 0.006), rect_loop(*fr_o, -0.035), rect_loop(*fr_i, -0.035), rect_loop(*fr_i, 0.006)], M["trim"], cap=False, smooth_angle=20)
ramp_parts = []
xs_d = [lerp(RX0, RX1, k / 6) for k in range(7)]
ramp_parts.append(loft("BoardingRamp", [[(x, RW, belly_z(x) + 0.004), (x, -RW, belly_z(x) + 0.004), (x, -RW, belly_z(x) - 0.024), (x, RW, belly_z(x) - 0.024)] for x in xs_d],
                       M["hull_dark"], bevel=0.004, smooth_angle=20))
for k_, (xa, xb) in enumerate(((RX0 - 0.06, 0.45), (0.37, -0.55), (-0.63, RX1 + 0.12))):   # raised plates on the outer face
    ramp_parts.append(loft(f"BoardingRampPlate_{k_}", [[(x, RW - 0.05, belly_z(x) - 0.022), (x, -RW + 0.05, belly_z(x) - 0.022), (x, -RW + 0.05, belly_z(x) - 0.034),
                                                         (x, RW - 0.05, belly_z(x) - 0.034)] for x in (xa, (xa + xb) / 2, xb)], M["hull"], bevel=0.003, smooth_angle=20))
for k_ in range(9):   # non-slip ribs across the middle plate
    x = lerp(0.3, -0.5, k_ / 8)
    ramp_parts.append(box(f"BoardingRampRib_{k_}", (x, 0, belly_z(x) - 0.038), (0.025, 2 * RW - 0.16, 0.01), M["trim"]))
for k_, (y0, y1) in enumerate(((-RW + 0.02, -0.15), (-0.08, 0.08), (0.15, RW - 0.02))):   # hinge knuckles (door-side) + frame-side
    cyl(f"RampHingeKnuckle_{k_}", (RX1 - 0.03, (y0 + y1) / 2, belly_z(RX1) - 0.02), 0.03, y1 - y0, M["gun"], axis="Y", verts=10)
for sy in (1, -1):   # actuator housings on the frame sides near the hinge, with piston rods, and threshold lights
    side_prism(f"RampActuator_{sy}", [(RX1 + 0.05, belly_z(RX1) + 0.0), (RX1 + 0.75, belly_z(RX1 + 0.75) + 0.0), (RX1 + 0.68, belly_z(RX1 + 0.68) - 0.07),
                                      (RX1 + 0.1, belly_z(RX1 + 0.1) - 0.07)], sy * (RW + 0.015), sy * (RW + 0.075), M["hull_dark"], bevel=0.006)
    cyl(f"RampPiston_{sy}", (RX1 + 0.9, sy * (RW + 0.045), belly_z(RX1 + 0.9) - 0.035), 0.012, 0.3, M["gun"], verts=8)
    for k_, x in enumerate((RX0 + 0.04, RX1 - 0.04)):
        box(f"RampThresholdLamp_{k_}_{sy}", (x, sy * (RW + 0.035), belly_z(x) - 0.037), (0.05, 0.05, 0.006), M["glow"])
box("RampHingeLamp", (RX1 - 0.065, 0, belly_z(RX1) - 0.037), (0.02, 2 * RW - 0.3, 0.006), M["glow"])
BOARDING_RAMP_PARTS = [o.name for o in ramp_parts]

# =================================================================== r11: man-sized top access hatch on the roof block aft of the turret
HX, HZ = -2.62, 2.07
cyl("TopHatchRimBase", (HX, 0, HZ + 0.005), 0.46, 0.03, M["hull_dark"], axis="Z", verts=32)
loft("TopHatchRim", [[(HX + r * math.cos(a_), r * math.sin(a_), HZ + z) for a_ in [k * 2 * math.pi / 32 for k in range(32)]]
                     for r, z in ((0.43, 0.0), (0.43, 0.045), (0.405, 0.07), (0.355, 0.07), (0.345, 0.03))], M["trim"], cap=False, smooth_angle=30)
cyl("TopHatchLid", (HX, 0, HZ + 0.04), 0.335, 0.05, M["hull"], axis="Z", verts=32)
cyl("TopHatchLidPlate", (HX, 0, HZ + 0.07), 0.27, 0.012, M["hull_dark"], axis="Z", verts=32)
# locking wheel: ring + 4 spokes + hub
loft("TopHatchWheel", [[(HX + r * math.cos(a_), r * math.sin(a_), HZ + z) for a_ in [k * 2 * math.pi / 20 for k in range(20)]]
                       for r, z in ((0.15, 0.085), (0.15, 0.115), (0.125, 0.115), (0.125, 0.085))], M["gun"], cap=False, smooth_angle=30)
for k_ in range(4):
    a_ = k_ * math.pi / 2 + math.pi / 4
    box(f"TopHatchSpoke_{k_}", (HX + 0.07 * math.cos(a_), 0.07 * math.sin(a_), HZ + 0.095), (0.12, 0.018, 0.016), M["gun"], rot=(0, 0, a_))
cyl("TopHatchHub", (HX, 0, HZ + 0.1), 0.035, 0.04, M["gun"], axis="Z", verts=12)
# hinge on the aft side, latch dogs around the rim, small status light ahead of the hatch
box("TopHatchHingeBlock", (HX - 0.44, 0, HZ + 0.04), (0.08, 0.3, 0.06), M["hull_dark"], bevel=0.006)
cyl("TopHatchHingePin", (HX - 0.4, 0, HZ + 0.075), 0.022, 0.34, M["gun"], axis="Y", verts=10)
for k_, a_ in enumerate((math.pi * 0.25, math.pi * 0.75, -math.pi * 0.75, -math.pi * 0.25, 0.0)):
    box(f"TopHatchDog_{k_}", (HX + 0.39 * math.cos(a_), 0.39 * math.sin(a_), HZ + 0.08), (0.06, 0.035, 0.025), M["hull_dark"], rot=(0, 0, a_))
box("TopHatchLamp", (HX + 0.5, 0, HZ + 0.012), (0.04, 0.16, 0.02), M["glow"])

# =================================================================== apply modifiers, cleanup, export
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(ROOT.children):
    if ob.type == "MESH" and ob.modifiers:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        old = ob.data; ob.modifiers.clear(); ob.data = me; bpy.data.meshes.remove(old)
for c in cutters: bpy.data.objects.remove(c)
# r12b (markup_overdetail_r12, owner): small modelled greebles go -- that detail comes from textures later. Bolts, framed access
# panels, louvre ribs/slats on vent panels, seam strips/strakes, bands and latch dogs are dropped; their base plates stay as one
# clean bevelled plate. Major features (ramp, top hatch, RCS, nav pods, engines, ion bank, bay louvres, cockpit, turret, fins) stay.
GREEBLE_DROP = ("PlainFrame_", "PlainHatch_", "PlainBolt_", "PlainStep_", "PlainStepBolt_", "PlainVent_", "PlainVentRib_", "PlainSeam_",
                "ShoulderVentRib_", "ShoulderVentRib2_", "ShoulderStrake_", "RootVentRib_", "WingSlotRib_", "RoofVentSlat_", "SideVentSlat_",
                "WingTipSeam_", "WingTipBand_", "TopHatchDog_")
for o in [o for o in ROOT.children if o.name.startswith(GREEBLE_DROP)]: bpy.data.objects.remove(o, do_unlink=True)
exec(open("/workspace/3d-output/work11/seat.py").read())     # r11: nudge small floating greebles onto the surface they belong to
exec(open("/workspace/3d-output/work11/fix12b.py").read())   # r12b: lamp re-seats from the diag review
if "--audit" in argv: exec(open("/workspace/3d-output/work11/audit.py").read())
if "--pick" in argv: exec(open("/workspace/3d-output/work11/pick.py").read())
if "--diag" in argv or "--diag-overview" in argv or "--diag-close" in argv: exec(open("/workspace/3d-output/work11/diag.py").read())
if "--audit-only" in argv: raise SystemExit
bpy.data.collections.remove(CUTTERS)

def join_all():
    groups = {}
    # r11: boarding ramp stays a separate object (origin on its hinge line) so it can be posed open later
    rp = [bpy.data.objects[n] for n in BOARDING_RAMP_PARTS]
    bpy.ops.object.select_all(action="DESELECT")
    for o in rp: o.select_set(True)
    bpy.context.view_layer.objects.active = rp[0]; bpy.ops.object.join(); ramp = rp[0]; ramp.name = "BoardingRamp"
    hinge = Vector((RX1, 0.0, belly_z(RX1) - 0.01))
    ramp.data.transform(Matrix.Translation(-hinge)); ramp.location = hinge
    for ob in ROOT.children:
        if ob.type == "MESH" and ob.name != "BoardingRamp": groups.setdefault(ob.data.materials[0].name if ob.data.materials else "none", []).append(ob)
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
    light("Under", "AREA", (2, 3, -12), 0, 10)
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
if "--probe" in argv:   # audit helper: small close-ups at points the checker flagged (PROBES="name:x,y,z,yaw,pitch,dist;...")
    setup_render((640, 400), False); os.makedirs(os.path.join(OUT, "work11/probes"), exist_ok=True)
    for spec in os.environ.get("PROBES", "").split(";"):
        if not spec: continue
        nm, v = spec.split(":"); x, y, z, yw, pt, ds = map(float, v.split(","))
        bpy.data.lights["Under"].energy = 1500 if pt < -20 else 0
        place_cam(yaw=yw, pitch=pt, dist=ds, lens=60, tx=x, ty=y, tz=z); render(os.path.join(OUT, "work11/probes", nm + ".png"))
if "--previews" in argv:
    setup_render((1280, 720), False)
    ONLY = [n for n in arg("--only", "").split(",") if n]
    for name, c in {"preview_front34": SRC_CAM,
                    "preview_side": dict(yaw=0, pitch=4, dist=27, lens=60, tz=0.2, tx=-0.6),
                    "preview_rear34": dict(yaw=-130, pitch=18, dist=27, lens=60, tz=0.2, tx=-0.6),
                    "preview_top": dict(yaw=0, pitch=89.5, dist=30, lens=60, tx=-0.6, roll=0),
                    "preview_under": dict(yaw=30, pitch=-35, dist=27, lens=60, tz=0.0, tx=-0.6),
                    "preview_back": dict(yaw=-90, pitch=10, dist=27, lens=60, tz=0.3, tx=0),
                    "preview_cockpit": dict(yaw=40, pitch=18, dist=7.5, lens=60, tx=3.2, ty=0.5, tz=1.0),
                    "preview_cockpit2": dict(yaw=75, pitch=25, dist=7.0, lens=60, tx=3.6, ty=0.0, tz=0.9),
                    "preview_rcs": dict(yaw=62, pitch=-6, dist=8, lens=60, tx=4.2, ty=1.0, tz=-0.3),
                    "preview_wingroot": dict(yaw=-90, pitch=8, dist=7, lens=60, tx=-5.8, ty=-1.6, tz=0.3),
                    "preview_rearshoulder": dict(yaw=40, pitch=14, dist=7, lens=60, tx=-5.0, ty=0.8, tz=1.3),
                    "preview_bottom": dict(yaw=0, pitch=-89.5, dist=30, lens=60, tx=-0.3),
                    "preview_bottom34": dict(yaw=35, pitch=-28, dist=26, lens=60, tx=-0.4, tz=0.0),
                    "preview_rcstop": dict(yaw=0, pitch=89.5, dist=36, lens=60, tx=-0.6, roll=0),
                    "preview_rcsbottom": dict(yaw=0, pitch=-89.5, dist=36, lens=60, tx=-0.6),
                    "preview_rcsside": dict(yaw=0, pitch=4, dist=27, lens=60, tz=0.2, tx=-0.6),
                    "preview_rcspod": dict(yaw=35, pitch=22, dist=2.0, lens=60, tx=-4.92, ty=5.0, tz=0.39),
                    "preview_rcspod2": dict(yaw=-35, pitch=18, dist=2.2, lens=60, tx=-6.68, ty=1.05, tz=0.4),
                    "preview_apillar": dict(yaw=38, pitch=10, dist=6.5, lens=60, tx=3.9, ty=0.6, tz=0.85),
                    "preview_plainside": dict(yaw=40, pitch=14, dist=4.0, lens=60, tx=-3.9, ty=1.5, tz=1.25),
                    "preview_overlapspot": dict(yaw=40, pitch=16, dist=4.2, lens=60, tx=-5.0, ty=1.5, tz=1.25),
                    "preview_tophatch": dict(yaw=55, pitch=35, dist=6, lens=60, tx=-2.4, ty=0, tz=2.0),
                    "preview_navlights": dict(yaw=-120, pitch=10, dist=9, lens=60, tx=-6.5, ty=0, tz=0.6),
                    "preview_navleft": dict(yaw=0, pitch=0, dist=27, lens=60, tz=0.4, tx=-0.6),
                    "preview_navright": dict(yaw=180, pitch=0, dist=27, lens=60, tz=0.4, tx=-0.6),
                    "preview_navback": dict(yaw=-90, pitch=0, dist=27, lens=60, tz=0.4, tx=0),
                    "preview_navtipclose": dict(yaw=35, pitch=8, dist=3.0, lens=60, tx=-4.3, ty=4.9, tz=0.4),
                    "preview_navsternclose": dict(yaw=-125, pitch=12, dist=3.0, lens=60, tx=-7.1, ty=0, tz=1.2),
                    "preview_ramp": dict(yaw=40, pitch=-35, dist=8, lens=60, tx=0.0, ty=0, tz=-1.2),
                    "preview_wingrear": dict(yaw=-112, pitch=16, dist=7, lens=60, tx=-5.6, ty=-3.3, tz=0.35),
                    "preview_clipfix": dict(yaw=-158, pitch=14, dist=10, lens=60, tx=0.1, ty=-1.0, tz=1.1),
                    "preview_bay": dict(yaw=12, pitch=10, dist=9, lens=60, tx=-0.15, tz=1.0),
                    "preview_wingtip": dict(yaw=-128, pitch=24, dist=8, lens=60, tx=-4.9, ty=-4.1, tz=0.4),
                    **({"preview_aftclose": dict(yaw=-140, pitch=15, dist=14, lens=60, tz=0.4, tx=-5.5),
                        "preview_backclose": dict(yaw=-90, pitch=5, dist=14, lens=60, tz=0.4, tx=-5.5, ty=0)} if "--close" in argv else {})}.items():
        if name in ("preview_under",) and "--extra" not in argv: continue
        if ONLY and name[8:] not in ONLY: continue
        bpy.data.lights["Under"].energy = 1500 if name.startswith(("preview_bottom", "preview_ramp", "preview_rcsbottom")) else 0
        place_cam(**c); render(os.path.join(OUT, name + SUFFIX + ".png"))
        if name.startswith("preview_rcs") and "pod" not in name:   # r13: pod screen positions for the RCS layout sheet
            import json; from bpy_extras.object_utils import world_to_camera_view as _w2c
            _pj = json.load(open(os.path.join(OUT, "work11", "rcs_proj.json"))) if os.path.exists(os.path.join(OUT, "work11", "rcs_proj.json")) else {}
            _pj[name] = [(r_[0], list(_w2c(scene, scene.camera, Vector(r_[1])))) for r_ in RCS_LOG]
            _pj["pods"] = RCS_LOG; json.dump(_pj, open(os.path.join(OUT, "work11", "rcs_proj.json"), "w"))
