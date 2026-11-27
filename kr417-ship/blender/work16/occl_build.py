import bpy, sys, os
OUT="/workspace/3d-output"
files=["plume_t025","plume_t050","plume_t075","plume_t100","plume_ion"]+[f"rcs_{g}" for g in ("pitch_pos","pitch_neg","yaw_pos","yaw_neg","roll_pos","roll_neg")]
# 1. build occluder mesh from the r15 hull (everything but plumes and RCS glow discs)
bpy.ops.wm.open_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
dg=bpy.context.evaluated_depsgraph_get()
import bmesh
bm=bmesh.new()
for o in bpy.data.objects:
    if o.type!="MESH" or o.name.startswith("Plume_") or o.name=="RCSGlow_Discs" or o.name=="BoundsMarker": continue
    if not o.visible_get(): continue
    me=o.evaluated_get(dg).to_mesh(); me.transform(o.matrix_world); bm.from_mesh(me); o.evaluated_get(dg).to_mesh_clear()
bmesh.ops.triangulate(bm,faces=bm.faces[:])
print("OCC tris",len(bm.faces))
verts=[v.co.copy() for v in bm.verts]; faces=[[v.index for v in f.verts] for f in bm.faces]; bm.free()
for f in files:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=f"{OUT}/{f}.glb")
    me=bpy.data.meshes.new("HullOccluder"); me.from_pydata([v[:] for v in verts],[],faces)
    m=bpy.data.materials.new("kr_occluder"); m.use_nodes=True; bs=m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value=(0,0,0,1); bs.inputs["Roughness"].default_value=1.0; m.use_backface_culling=False
    me.materials.append(m); me.uv_layers.new(name="UVMap")
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("HullOccluder",me))
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{f}_occ.glb", export_format="GLB", export_image_format="AUTO", export_cameras=False,
        export_lights=False, export_apply=True, use_selection=False, export_yup=True, export_normals=False)
print("DONE")
