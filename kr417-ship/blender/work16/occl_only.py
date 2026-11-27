import bpy, bmesh
OUT="/workspace/3d-output"
bpy.ops.wm.open_mainfile(filepath=f"{OUT}/spaceship_r15.blend")
dg=bpy.context.evaluated_depsgraph_get(); bm=bmesh.new()
for o in bpy.data.objects:
    if o.type!="MESH" or o.name.startswith("Plume_") or o.name=="RCSGlow_Discs" or not o.visible_get(): continue
    me=o.evaluated_get(dg).to_mesh(); me.transform(o.matrix_world); bm.from_mesh(me); o.evaluated_get(dg).to_mesh_clear()
bmesh.ops.triangulate(bm,faces=bm.faces[:]); bmesh.ops.remove_doubles(bm,verts=bm.verts[:],dist=1e-5)
verts=[v.co.copy() for v in bm.verts]; faces=[[v.index for v in f.verts] for f in bm.faces]; bm.free()
bpy.ops.wm.read_factory_settings(use_empty=True)
me=bpy.data.meshes.new("HullOccluder"); me.from_pydata([v[:] for v in verts],[],faces)
m=bpy.data.materials.new("kr_occluder"); me.materials.append(m); me.uv_layers.new(name="UVMap")
bpy.context.scene.collection.objects.link(bpy.data.objects.new("HullOccluder",me))
bpy.ops.export_scene.gltf(filepath=f"{OUT}/work16/occluder.glb", export_format="GLB", export_cameras=False, export_lights=False, export_yup=True)
print("OCC",len(verts),len(faces))
