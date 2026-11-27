import bpy, bmesh, os, json, numpy as np
from mathutils import Vector
OUT="/workspace/3d-output"; T2=f"{OUT}/work14/tex2k"; W=f"{OUT}/work16"
rep=json.load(open(f"{OUT}/r15_report.json")); B=json.load(open(f"{W}/bounds.json"))
RCS=[n for n in rep["nozzles"] if n["name"].startswith("RCS")]
# ---- torque classification (Blender axes: X nose, Y port, Z up). pitch+ = torque -Y, yaw+ = +Z, roll+ = +X
GROUPS={g:[] for g in ("pitch_pos","pitch_neg","yaw_pos","yaw_neg","roll_pos","roll_neg")}
TQ={}
for n in RCS:
    r=np.array(n["exit_blender"]); F=-np.array(n["dir_blender"]); t=np.cross(r,F)
    ax={"pitch":-t[1],"yaw":t[2],"roll":t[0]}; TQ[n["name"]]={k:round(float(v),2) for k,v in ax.items()}
    mx=max(abs(ax["pitch"]),abs(ax["yaw"]))
    for k in ("pitch","yaw"):
        v=ax[k]
        if abs(v)>=1.0 and abs(v)>=0.5*mx: GROUPS[f"{k}_{'pos' if v>0 else 'neg'}"].append(n["name"])
    # roll: vertical (pitch-primary) jets off the centreline, fired in diagonal pairs whose pitch cancels
    if abs(ax["roll"])>=1.0 and abs(ax["pitch"])>=abs(ax["yaw"]): GROUPS[f"roll_{'pos' if ax['roll']>0 else 'neg'}"].append(n["name"])
NET={g:{k:round(sum(TQ[n][k] for n in L),2) for k in ("pitch","yaw","roll")} for g,L in GROUPS.items()}
print("NET",json.dumps(NET))
json.dump({"groups":GROUPS,"torque":TQ,"net_torque":NET},open(f"{W}/rcs_groups.json","w"),indent=1)
print("GROUPS",json.dumps(GROUPS))
def to2k():
    for im in list(bpy.data.images):
        base=im.name.split(".")[0]
        for ext in (".jpg",".png"):
            f=f"{T2}/{base}{ext}"
            if os.path.exists(f):
                new=bpy.data.images.load(f); new.colorspace_settings.name=im.colorspace_settings.name; im.user_remap(new); break
def export(path):
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", export_image_format="AUTO", export_tangents=True, export_cameras=False,
        export_lights=False, export_apply=True, use_selection=False, export_yup=True)
def openb(): bpy.ops.wm.open_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
def marker(mat):
    e=1e-4; verts=[]; faces=[]
    for c,s in ((Vector(B["plume_min"]),1),(Vector(B["plume_max"]),-1)):
        i=len(verts); verts+=[c,c+Vector((s*e,0,0)),c+Vector((0,s*e,0))]; faces.append((i,i+1,i+2))
    me=bpy.data.meshes.new("BoundsMarker"); me.from_pydata([v[:] for v in verts],[],faces); me.materials.append(mat); me.uv_layers.new(name="UVMap")
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("BoundsMarker",me))
def strip(keep):
    for o in list(bpy.data.objects):
        if o.type=="MESH" and not keep(o): bpy.data.objects.remove(o,do_unlink=True)
        elif o.type=="EMPTY" and o.name.startswith("pod_"): bpy.data.objects.remove(o,do_unlink=True)
# ---- per-group RCS files: plumes + glow discs (own material, tinted 4x4 texture)
openb()
disc=bpy.data.objects["RCSGlow_Discs"]; bm=bmesh.new(); bm.from_mesh(disc.data); bm.transform(disc.matrix_world)
parts={}  # nozzle -> list of face vertex coords
for f in bm.faces:
    c=f.calc_center_median()
    best=min(RCS,key=lambda n:(Vector(n["exit_blender"])-c).length)
    parts.setdefault(best["name"],[]).append([v.co.copy() for v in f.verts])
print("DISC parts",len(parts),{k:len(v) for k,v in list(parts.items())[:3]})
bm.free()
for g,names in GROUPS.items():
    openb()
    strip(lambda o:o.name in [f"Plume_{n}" for n in names])
    tp=bpy.data.materials["kr_thruster_plume"]
    img=bpy.data.images.new("rcs_tint",4,4); img.pixels=[0xbf/255,0xe0/255,1.0,1.0]*16; img.pack()
    m=bpy.data.materials.new("rcs_glow"); m.use_nodes=True; nt=m.node_tree; bs=nt.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value=(0.02,0.02,0.02,1); tx=nt.nodes.new("ShaderNodeTexImage"); tx.image=img
    nt.links.new(tx.outputs["Color"],bs.inputs["Emission Color"]); bs.inputs["Emission Strength"].default_value=8.0
    bm=bmesh.new()
    for n in names:
        for f in parts[n]: bm.faces.new([bm.verts.new(v) for v in f])
    me=bpy.data.meshes.new(f"RCSGlow_{g}"); bm.to_mesh(me); bm.free(); me.materials.append(m); me.uv_layers.new(name="UVMap")
    bpy.context.scene.collection.objects.link(bpy.data.objects.new(f"RCSGlow_{g}",me))
    marker(tp); export(f"{OUT}/rcs_{g}.glb")
print("DONE")
