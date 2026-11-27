import bpy, os, sys, numpy as np, json
from mathutils import Vector
OUT="/workspace/3d-output"; T2=f"{OUT}/work14/tex2k"
def bb(f):
    P=np.array([(o.matrix_world@v.co)[:] for o in bpy.data.objects if o.type=="MESH" and f(o) for v in o.data.vertices]); return P.min(0),P.max(0)
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
isplume=lambda o:o.name.startswith("Plume_")
# --- ship (no plumes)
bpy.ops.wm.open_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
mn,mx=bb(lambda o: not isplume(o)); amn,amx=bb(lambda o:True)
print("SHIPBB",mn.round(4),mx.round(4)," ALLBB",amn.round(4),amx.round(4))
json.dump({"min":mn.tolist(),"max":mx.tolist()},open("shipbb.json","w"))
for o in [o for o in bpy.data.objects if isplume(o)]: bpy.data.objects.remove(o,do_unlink=True)
to2k(); export(f"{OUT}/spaceship_r15_ship_2k.glb")
# --- plumes only + bounds marker
bpy.ops.wm.open_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
root=bpy.data.objects["Spaceship"]
plmat=None
for o in list(bpy.data.objects):
    if o.type=="MESH" and not isplume(o): bpy.data.objects.remove(o,do_unlink=True)
    elif o.type=="EMPTY" and o.name.startswith("pod_"): bpy.data.objects.remove(o,do_unlink=True)
for o in bpy.data.objects:
    if isplume(o): plmat=o.data.materials[0]
e=1e-4; verts=[]; faces=[]
for c in (mn,mx):
    c=Vector(c); s=-1 if c is mx else 1
    i=len(verts); verts+= [c, c+Vector((s*e,0,0)), c+Vector((0,s*e,0))]; faces.append((i,i+1,i+2))
me=bpy.data.meshes.new("BoundsMarker"); me.from_pydata([v[:] for v in verts],[],faces); me.materials.append(plmat); me.uv_layers.new(name="UVMap")
bo=bpy.data.objects.new("BoundsMarker",me); bpy.context.scene.collection.objects.link(bo)  # world coords, no parent (root is identity)
pmn,pmx=bb(lambda o:True); print("PLUMEFILEBB",pmn.round(4),pmx.round(4))
export(f"{OUT}/ship_plumes.glb")
print("DONE")
