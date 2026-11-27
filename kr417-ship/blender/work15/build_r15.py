# r15: split glow materials, real-geometry ion plumes, wingtip pod emitters + pod_L/pod_R empties
import bpy, bmesh, math, json, sys, os
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
OUT = "/workspace/3d-output"; W = f"{OUT}/work15"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=f"{OUT}/spaceship_r14b.glb")
ROOT = bpy.data.objects["Spaceship"]; assert ROOT.matrix_world == Matrix.Identity(4)
sc = bpy.context.scene
REPORT = {"nozzles": [], "pods": {}, "notes": []}

# ---------- ship BVH (all opaque ship meshes) for ray checks
def ship_bvh():
    bm = bmesh.new()
    for o in bpy.data.objects:
        if o.type == "MESH" and not o.name.startswith(("Plume", "PodGlow", "RCSGlow")):
            t = bmesh.new(); t.from_mesh(o.data); t.transform(o.matrix_world)
            me = bpy.data.meshes.new("tmp"); t.to_mesh(me); bm.from_mesh(me); bpy.data.meshes.remove(me); t.free()
    return BVHTree.FromBMesh(bm)
BVH = ship_bvh()
def clear_run(p, d, maxd=3.0):
    hit = BVH.ray_cast(Vector(p), Vector(d).normalized(), maxd)
    return maxd if hit[0] is None else (hit[0] - Vector(p)).length

def loose_parts(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.faces.ensure_lookup_table()
    seen = set(); res = []
    for f in bm.faces:
        if f.index in seen: continue
        st = [f]; comp = []; seen.add(f.index)
        while st:
            g = st.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); st.append(h)
        res.append(comp)
    return bm, res

# ---------- 1. materials: split glow
FX = bpy.data.materials["Lights_Interior"]
def dup(name):
    m = FX.copy(); m.name = name; return m
M_ENG_GLOW = dup("kr_engine_glow"); M_THR_GLOW = dup("kr_thruster_glow")
def in_thruster(c):
    return (abs(c.x + 5.68) < 0.05 and abs(abs(c.y) - 1.72) < 0.45 and abs(c.z - 0.6) < 0.1) or \
           (abs(c.x + 4.0) < 0.03 and abs(abs(c.y) - 2.22) < 0.1 and abs(c.z + 0.56) < 0.1)
cnt = {"engine": 0, "thruster": 0}
for on in ("Ship_EngineGlow", "Ship_EngineGlowAft"):
    o = bpy.data.objects[on]; me = o.data
    me.materials.append(M_ENG_GLOW); me.materials.append(M_THR_GLOW)
    ie, it = len(me.materials) - 2, len(me.materials) - 1
    for p in me.polygons:
        c = o.matrix_world @ p.center
        if in_thruster(c): p.material_index = it; cnt["thruster"] += 1
        else: p.material_index = ie; cnt["engine"] += 1
    # drop the now unused Lights_Interior slot
    o.active_material_index = 0; bpy.context.view_layer.objects.active = o
    o.select_set(True); bpy.ops.object.material_slot_remove_unused(); o.select_set(False)
print("GLOWFACES", cnt)
# UV of a plain glowing texel (pod-end glow cap) for the RCS throat discs
o = bpy.data.objects["Ship_EngineGlowAft"]; uvl = o.data.uv_layers.active.data; acc = Vector((0, 0)); n = 0
for p in o.data.polygons:
    c = o.matrix_world @ p.center
    if abs(c.x + 4.006) < 0.004 and abs(c.y - 2.22) < 0.02 and abs(c.z + 0.56) < 0.02:
        for li in p.loop_indices: acc += uvl[li].uv; n += 1
GLOW_UV = acc / n; print("GLOW_UV", GLOW_UV, n)

# ---------- plume texture (RGBA): u bands core|mid|halo, v = 0 at nozzle .. 1 at tip
TW, TH = 128, 256
img = bpy.data.images.new("kr_plume_grad", TW, TH, alpha=True)
px = np.zeros((TH, TW, 4), np.float32)
def srgb(h): return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
C_HOT, C_CORE, C_BLUE, C_DEEP = srgb("eef7ff"), srgb("bfe0ff"), srgb("5fa8ff"), srgb("3a6dff")
NSH = 8
SH_R = [0.22 + 0.78 * i / (NSH - 1) for i in range(NSH)]
def _mixc(a, b, f): return a + (b - a) * f
BANDS = []   # (alpha at nozzle, falloff power, colour stops) core -> outer halo
for i, rk in enumerate(SH_R):
    f = i / (NSH - 1)
    BANDS.append((0.03 + 0.30 * (1 - rk) ** 1.4 / 0.78 ** 1.4 * 1.0, 1.5 - 0.5 * f,
                  (_mixc(C_HOT, C_BLUE, f), _mixc(C_CORE, C_DEEP, f), _mixc(C_BLUE, C_DEEP, min(1, f * 2)))))

for j in range(TH):
    t = (j + 0.5) / TH
    ramp_in = min(1.0, t / 0.04)
    for b, (a0, pw, cs) in enumerate(BANDS):
        col = cs[0] + (cs[1] - cs[0]) * min(1, t / 0.35) if t < 0.35 else cs[1] + (cs[2] - cs[1]) * ((t - 0.35) / 0.65)
        a = a0 * (1 - t) ** pw * ramp_in
        fade = (1 - t) ** 0.6   # emissive rgb also fades so the tip is dark even if alpha were ignored
        for i in range(b * TW // len(BANDS), (b + 1) * TW // len(BANDS)):
            px[j, i, :3] = col * fade; px[j, i, 3] = a
img.pixels = px.ravel(); img.filepath_raw = f"{W}/kr_plume_grad.png"; img.file_format = "PNG"; img.save(); img.pack()
BAND_U = [(b + 0.5) / len(BANDS) for b in range(len(BANDS))]
EMIT_PLUME = 6.0
def plume_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear(); L = nt.links.new
    out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled"); L(b.outputs[0], out.inputs[0])
    tx = nt.nodes.new("ShaderNodeTexImage"); tx.image = img; tx.interpolation = "Linear"; tx.extension = "EXTEND"
    L(tx.outputs["Color"], b.inputs["Base Color"]); L(tx.outputs["Alpha"], b.inputs["Alpha"])
    L(tx.outputs["Color"], b.inputs["Emission Color"]); b.inputs["Emission Strength"].default_value = EMIT_PLUME
    b.inputs["Roughness"].default_value = 1.0; b.inputs["Metallic"].default_value = 0.0
    m.blend_method = "BLEND"; m.surface_render_method = "BLENDED"; m.use_backface_culling = False; m.use_transparency_overlap = True
    return m
M_ENG_PLUME = plume_mat("kr_engine_plume"); M_THR_PLUME = plume_mat("kr_thruster_plume")
def flat_emit_mat(name, base, emit, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*base, 1); b.inputs["Roughness"].default_value = 0.35; b.inputs["Metallic"].default_value = 0.0
    b.inputs["Emission Color"].default_value = (*emit, 1); b.inputs["Emission Strength"].default_value = strength
    return m
def lin(h): return tuple(((c / 255 + 0.055) / 1.055) ** 2.4 if c / 255 > 0.04045 else c / 255 / 12.92 for c in (int(h[i:i + 2], 16) for i in (0, 2, 4)))
M_POD = flat_emit_mat("kr_pod_glow", (0.03, 0.06, 0.12), lin("5fa8ff"), 6.0)

# ---------- 2. nozzle discovery (geometry)
def cone_axis(comp):
    vs = list({v for f in comp for v in f.verts}); P = np.array([v.co[:] for v in vs])
    N = np.array([f.normal[:] for f in comp]); A = np.array([f.calc_area() for f in comp])
    C = (N * A[:, None]).T @ N; w, V = np.linalg.eigh(C); ax = Vector(V[:, 0]).normalized()
    c = Vector(P.mean(0)); s = (P - np.array(c[:])) @ np.array(ax[:])
    lo, hi = P[s < 0], P[s >= 0]
    def ring(Q):
        cc = Vector(Q.mean(0)); r = float(np.mean(np.linalg.norm(Q - np.array(cc[:]) - np.outer((Q - np.array(cc[:])) @ np.array(ax[:]), ax[:]), axis=1)))
        return cc, r
    (c1, r1), (c2, r2) = ring(lo), ring(hi)
    if r1 > r2: (c1, r1), (c2, r2) = (c2, r2), (c1, r1)
    d = (c2 - c1).normalized()
    return dict(throat=c1, r_throat=r1, exit=c2, r_exit=r2, dir=d, nv=len(vs))
bmg, gparts = loose_parts(bpy.data.objects["Ship_GunMetal"])
rcs, bells = [], []
for comp in gparts:
    nv = len({v for f in comp for v in f.verts})
    if nv == 20 and len(comp) == 20: rcs.append(cone_axis(comp))
    elif nv == 56 and len(comp) == 56:
        k = cone_axis(comp)
        if k["r_exit"] > 0.3: bells.append(k)
print("FOUND rcs", len(rcs), "bells", len(bells), [ (tuple(round(x,3) for x in b['exit']), round(b['r_exit'],3)) for b in bells])
assert len(bells) == 2, bells

NOZ = []   # (name, kind, start, exit, dir, (ry,rz) at start, (ry,rz) at exit, length past exit, up-vector, segments)
for b in sorted(bells, key=lambda k: -k["exit"].y):
    side = "L" if b["exit"].y > 0 else "R"
    # throat glow disc sits at x=-6.9; start the plume just behind it inside the bell
    st = Vector((-6.93, b["exit"].y, b["exit"].z)); rs = 0.26 + 0.14 * (6.93 - 6.65) / 0.7
    NOZ.append(dict(name=f"Main_{side}", kind="engine", start=st, exit=b["exit"], dir=b["dir"], r0=(rs * 0.92, rs * 0.92), r1=(b["r_exit"] * 0.9, b["r_exit"] * 0.9), L=1.75, seg=28, src="MainBell cone (gun metal), exit ring r=%.3f" % b["r_exit"]))
# flat glow plates: ion bank, impulse slot, wing-root thrusters, pod-engine ends -> exhaust dir by ray test
bme, eparts = loose_parts(bpy.data.objects["Ship_EngineGlowAft"])
plates = []
for comp in eparts:
    vs = {v for f in comp for v in f.verts}; P = np.array([v.co[:] for v in vs]); mn, mx = P.min(0), P.max(0); c = Vector((mn + mx) / 2); s = mx - mn
    plates.append((c, s))
def dir_by_ray(c, s):
    best = None
    for d in (Vector((-1, 0, 0)), Vector((1, 0, 0))):
        offs = [Vector((0, dy, dz)) for dy in (-0.3, 0, 0.3) for dz in (-0.3, 0, 0.3)]
        runs = [clear_run(c + Vector((0, o.y * s[1], o.z * s[2])) + d * 0.012, d) for o in offs]
        score = sum(runs) / len(runs)
        if best is None or score > best[0]: best = (score, d, runs)
    return best
for c, s in plates:
    score, d, runs = dir_by_ray(c, s)
    side = "L" if c.y > 0 else ("R" if c.y < 0 else "C")
    if abs(c.x + 5.485) < 0.01:        # ion-grid bank: plate at the channel back wall, nozzle exit flush with the lips at x=-5.67
        k = int(round((abs(c.y) - 2.523) / 0.3267)); hy, hz = s[1] / 2, s[2] / 2
        NOZ.append(dict(name=f"IonBank_{k}_{side}", kind="engine", start=c + d * 0.006, exit=Vector((-5.67, c.y, c.z)), dir=d, r0=(hy * 0.95, max(hz, 0.03) * 0.95), r1=(hy + 0.04, max(hz + 0.04, 0.05)), L=0.75, seg=16, src="IonGlowPlate", clear=runs))
    elif abs(c.x + 6.895) < 0.01 and s[1] > 1.0:       # impulse slit
        NOZ.append(dict(name="Impulse_C", kind="engine", start=c + d * 0.006, exit=Vector((-7.02, c.y, c.z)), dir=d, r0=(0.55, 0.05), r1=(0.56, 0.07), L=1.0, seg=28, src="ImpulseGlow", clear=runs))
    elif abs(c.x + 5.68) < 0.01:        # wing-root thrusters
        NOZ.append(dict(name=f"WingRoot_{side}", kind="thruster", start=c + d * 0.006, exit=Vector((-5.86, c.y, c.z)), dir=d, r0=(0.36, 0.12), r1=(0.38, 0.14), L=1.0, seg=24, src="RootNozzleGlow", clear=runs))
    elif abs(c.x + 4.0) < 0.01:         # pod-engine end caps
        NOZ.append(dict(name=f"PodEngineEnd_{side}", kind="thruster", start=c + d * 0.008, exit=c + d * 0.008, dir=d, r0=(0.055, 0.055), r1=(0.06, 0.06), L=0.38, seg=14, src="PodEndGlow", clear=runs))
    elif abs(c.x + 6.9) < 0.02 and s[1] < 0.6: pass   # main-bell throat discs (plumes come from the bell analysis)
    else: print("UNCLASSIFIED PLATE", c, s)
for i, r in enumerate(sorted(rcs, key=lambda k: (round(-k["exit"].x, 2), round(-k["exit"].y, 2), round(-k["exit"].z, 2)))):
    NOZ.append(dict(name=f"RCS_{i:02d}", kind="thruster", start=r["throat"], exit=r["exit"], dir=r["dir"], r0=(r["r_throat"] * 0.85,) * 2, r1=(r["r_exit"] * 0.85,) * 2, L=0.24, seg=12, src="RCS nozzle cone r %.3f->%.3f" % (r["r_throat"], r["r_exit"])))
# sanity: every exhaust must point into free space
for nz in NOZ:
    nz["free"] = clear_run(nz["exit"] + nz["dir"] * 0.01, nz["dir"], 3.0)
    if nz["free"] < nz["L"] * 0.5: print("WARNING plume blocked", nz["name"], nz["free"])

# ---------- plume mesh: 3 nested elliptical shells, rings along the exhaust axis
def basis(d):
    d = d.normalized(); up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((0, 1, 0))
    a = up.cross(d).normalized(); b = d.cross(a).normalized(); return a, b   # a ~ "y" (horizontal), b ~ "z" (vertical-ish)
SHELLS = [(rk, 0.9 + 0.18 * rk) for rk in SH_R]   # (radius scale, length scale) for core, mid, halo
def build_plume(nz):
    d = nz["dir"].normalized(); a, b = basis(d)
    s_exit = max(0.0, (nz["exit"] - nz["start"]).dot(d)); total = s_exit + nz["L"]
    # match the ellipse axes to the nozzle: for -X exhaust a = +/-Y, b = +Z
    bm = bmesh.new(); uv = bm.loops.layers.uv.new("UVMap"); seg = nz["seg"]; small = seg <= 14; NR = 9 if small else 14
    for si, (rk, lk) in enumerate(SHELLS):
        if small and si not in (0, 2, 5, 7): continue
        tot = s_exit + nz["L"] * lk; rings = []
        for k in range(NR + 1):
            t = k / NR; s = tot * (t ** 1.15)
            if s <= s_exit and s_exit > 0: f = s / s_exit; ry = nz["r0"][0] + (nz["r1"][0] - nz["r0"][0]) * f; rz = nz["r0"][1] + (nz["r1"][1] - nz["r0"][1]) * f
            else:
                f = (s - s_exit) / (tot - s_exit); sh = 1 - 0.85 * f ** 1.5
                ry, rz = nz["r1"][0] * sh, nz["r1"][1] * sh
                if s_exit == 0: ry, rz = nz["r0"][0] + (ry - nz["r0"][0]) * min(1, f * 6), nz["r0"][1] + (rz - nz["r0"][1]) * min(1, f * 6)
            ring = []
            for j in range(seg):
                th = 2 * math.pi * j / seg
                p = nz["start"] + d * s + a * (math.cos(th) * ry * rk) + b * (math.sin(th) * rz * rk)
                ring.append(bm.verts.new(p))
            rings.append((ring, s / total))
        for k in range(NR):
            (r0, v0), (r1, v1) = rings[k], rings[k + 1]
            for j in range(seg):
                f = bm.faces.new((r0[j], r0[(j + 1) % seg], r1[(j + 1) % seg], r1[j]))
                for l, vv in zip(f.loops, (v0, v0, v1, v1)): l[uv].uv = (BAND_U[si], vv)   # Blender v=0 = image row 0 = nozzle (exporter flips to glTF)
    me = bpy.data.meshes.new(f"Plume_{nz['name']}"); bm.normal_update(); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(M_ENG_PLUME if nz["kind"] == "engine" else M_THR_PLUME)
    o = bpy.data.objects.new(f"Plume_{nz['name']}", me); sc.collection.objects.link(o); o.parent = ROOT
    return o
for nz in NOZ: build_plume(nz)
# RCS throat glow discs (kr_thruster_glow) so the RCS jets have a nozzle glow that the warp can switch off too
bm = bmesh.new(); uvl = bm.loops.layers.uv.new("UVMap")
for nz in NOZ:
    if not nz["name"].startswith("RCS"): continue
    d = nz["dir"]; a, b = basis(d); c = nz["start"] + d * 0.004; r = nz["r0"][0] * 1.02
    vs = [bm.verts.new(c + a * math.cos(2 * math.pi * j / 10) * r + b * math.sin(2 * math.pi * j / 10) * r) for j in range(10)]
    f = bm.faces.new(vs)
    if f.normal.dot(d) < 0: f.normal_flip()
    for l in f.loops: l[uvl].uv = GLOW_UV
bmesh.ops.triangulate(bm, faces=bm.faces[:])
me = bpy.data.meshes.new("RCSGlow_Discs"); bm.to_mesh(me); bm.free(); me.materials.append(M_THR_GLOW)
o = bpy.data.objects.new("RCSGlow_Discs", me); sc.collection.objects.link(o); o.parent = ROOT

# ---------- 3. wingtip pod emitters (blue rings + outboard strips) and pod_L / pod_R
TB = [(-4.0, 0.16), (-4.0, 0.64), (-4.08, 0.72), (-5.62, 0.68), (-5.72, 0.58), (-5.72, 0.18), (-5.64, 0.08), (-4.08, 0.08)]; TBC = (-4.86, 0.4)
# verify the tip block profile against the real mesh: extents of hull verts in the tip region
P = []
for on in ("Ship_HullGreyDark", "Ship_HullGrey", "Ship_TrimDark"):
    ob = bpy.data.objects[on]
    for v in ob.data.vertices:
        w = ob.matrix_world @ v.co
        if 4.33 < w.y < 4.9 and -5.9 < w.x < -3.9 and -0.1 < w.z < 0.9: P.append(w[:])
P = np.array(P); print("TIPBLOCK_EXTENT x", P[:, 0].min(), P[:, 0].max(), "z", P[:, 2].min(), P[:, 2].max())
def tb_ring(y, k): return [(TBC[0] + (x - TBC[0]) * k, y, TBC[1] + (z - TBC[1]) * k) for x, z in TB]
def solid_ring(bm, y0, y1, k_in, k_out):
    secs = [tb_ring(y0, k_in), tb_ring(y0, k_out), tb_ring(y1, k_out), tb_ring(y1, k_in)]
    V = [[bm.verts.new(p) for p in s] for s in secs]; n = len(TB)
    for a_ in range(4):
        A, B = V[a_], V[(a_ + 1) % 4]
        for j in range(n): bm.faces.new((A[j], A[(j + 1) % n], B[(j + 1) % n], B[j]))
for sy, side in ((1, "L"), (-1, "R")):
    bm = bmesh.new()
    solid_ring(bm, 4.632, 4.688, 1.0, 1.048)     # over the trim band (band is k=1.03, y 4.60-4.72)
    solid_ring(bm, 4.855, 4.895, 0.985, 1.022)   # second ring near the outboard end
    # two emitter strips on the outboard face either side of the RCS housing
    xo = TIPY = 4.98
    for xc in (-4.47, -5.42):
        for p in [(xc - 0.05, 0.2), (xc + 0.05, 0.2), (xc + 0.05, 0.6), (xc - 0.05, 0.6)]: pass
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((xc, TIPY + 0.004, 0.4)) @ Matrix.Diagonal((0.09, 0.02, 0.36, 1)))
    if sy < 0: bmesh.ops.scale(bm, vec=(1, -1, 1), verts=bm.verts); bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(f"PodGlow_{side}"); bm.to_mesh(me); bm.free(); me.materials.append(M_POD)
    me.uv_layers.new(name="UVMap")
    o = bpy.data.objects.new(f"PodGlow_{side}", me); sc.collection.objects.link(o); o.parent = ROOT
    e = bpy.data.objects.new(f"pod_{side}", None); e.empty_display_type = "SPHERE"; e.empty_display_size = 0.15
    e.location = (-4.86, sy * 5.25, 0.40); sc.collection.objects.link(e); e.parent = ROOT
    REPORT["pods"][f"pod_{side}"] = dict(blender=list(e.location), center_of_pod_block=[-4.86, sy * 4.65, 0.40])
# confirm port/starboard: red nav light should be on +Y (left/port)
for on in ("Ship_NavRed", "Ship_NavGreen"):
    ob = bpy.data.objects[on]; ys = [(ob.matrix_world @ v.co).y for v in ob.data.vertices]; print("NAV", on, "mean y", sum(ys) / len(ys))

# ---------- report
def gl(v): return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]   # Blender Z-up -> glTF Y-up
for nz in NOZ:
    REPORT["nozzles"].append(dict(name=nz["name"], kind=nz["kind"], exit_blender=[round(x, 4) for x in nz["exit"]], dir_blender=[round(x, 4) for x in nz["dir"]],
                                  exit_gltf=gl(nz["exit"]), dir_gltf=gl(nz["dir"]), exit_radius=[round(x, 3) for x in nz["r1"]], plume_len_past_exit=nz["L"],
                                  free_space_along_exhaust=round(nz["free"], 3), source=nz["src"]))
for k, v in REPORT["pods"].items(): v["gltf"] = gl(v["blender"]); v["center_gltf"] = gl(v["center_of_pod_block"])
json.dump(REPORT, open(f"{W}/r15_report.json", "w"), indent=1)

# ---------- export (4K) + 2K variant, then patch the plume materials (black base, unlit)
for o in bpy.data.objects:
    if o.type == "MESH" and not o.data.uv_layers: o.data.uv_layers.new(name="UVMap")
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_image_format="AUTO", export_tangents=True, export_cameras=False,
                              export_lights=False, export_apply=True, use_selection=False, export_yup=True)
export(f"{OUT}/spaceship_r15.glb")
T2 = f"{OUT}/work14/tex2k"
for im in list(bpy.data.images):
    base = im.name.split(".")[0]
    for ext in (".jpg", ".png"):
        f = f"{T2}/{base}{ext}"
        if os.path.exists(f):
            new = bpy.data.images.load(f); new.colorspace_settings.name = im.colorspace_settings.name; im.user_remap(new); break
export(f"{OUT}/spaceship_r15_2k.glb")
print("DONE")
