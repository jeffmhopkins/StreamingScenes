import bpy, os, json
from mathutils import Vector
OUT="/workspace/3d-output"; T2=f"{OUT}/work14/tex2k"; W=f"{OUT}/work16"
rep={n["name"]:n for n in json.load(open(f"{OUT}/r15_report.json"))["nozzles"]}; B=json.load(open(f"{W}/bounds.json"))
MAIN=["Main_L","Main_R","Impulse_C","WingRoot_L","WingRoot_R","PodEngineEnd_L","PodEngineEnd_R"]
ION=[n for n in rep if n.startswith("IonBank")]
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
# ---- ship: no plumes, no RCS discs, ion plates on their own material
openb()
for o in [o for o in bpy.data.objects if o.name.startswith("Plume_") or o.name=="RCSGlow_Discs"]: bpy.data.objects.remove(o,do_unlink=True)
o=bpy.data.objects["Ship_EngineGlowAft"]; me=o.data
eng=bpy.data.materials["kr_engine_glow"]; ion=eng.copy(); ion.name="kr_ion_glow"; me.materials.append(ion); ii=len(me.materials)-1
ei=[i for i,m in enumerate(me.materials) if m and m.name=="kr_engine_glow"][0]; n=0
for p in me.polygons:
    c=o.matrix_world@p.center
    if p.material_index==ei and abs(c.x+5.485)<0.04 and 2.3<abs(c.y)<4.45: p.material_index=ii; n+=1
print("ION faces",n)
to2k(); export(f"{OUT}/spaceship_r15_ship_2k_d.glb")
# ---- plume tiers for the throttle set, scaled beyond each nozzle exit
for f in (0.25,0.5,0.75,1.0):
    openb(); keep=[f"Plume_{n}" for n in MAIN]; strip(lambda o:o.name in keep)
    for nm in MAIN:
        ob=bpy.data.objects[f"Plume_{nm}"]; ex=Vector(rep[nm]["exit_blender"]); d=Vector(rep[nm]["dir_blender"]).normalized()
        mw=ob.matrix_world; inv=mw.inverted()
        for v in ob.data.vertices:
            w=mw@v.co; s=(w-ex).dot(d)
            if s>0: v.co=inv@(w-d*s*(1-f))
    marker(bpy.data.materials["kr_engine_plume"]); export(f"{OUT}/plume_t{int(f*100):03d}.glb")
# ---- ion bank plumes
openb(); keep=[f"Plume_{n}" for n in ION]; strip(lambda o:o.name in keep); marker(bpy.data.materials["kr_engine_plume"]); export(f"{OUT}/plume_ion.glb")
print("DONE", len(ION))
