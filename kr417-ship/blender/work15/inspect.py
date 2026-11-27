import bpy, sys
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=sys.argv[-1])
for o in bpy.data.objects:
    print("OBJ", o.name, o.type, o.parent.name if o.parent else None, tuple(round(v,3) for v in o.location), [m.name for m in (o.data.materials if o.type=='MESH' else [])], len(o.data.polygons) if o.type=='MESH' else '')
for m in bpy.data.materials:
    print("MAT", m.name, m.users)
for im in bpy.data.images:
    print("IMG", im.name, im.size[:])
