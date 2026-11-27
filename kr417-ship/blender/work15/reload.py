import bpy, sys
for p in sys.argv[sys.argv.index("--") + 1:]:
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=p)
    print("FILE", p)
    print(" MATS", sorted(m.name for m in bpy.data.materials if m.users))
    print(" EMPTIES", [(o.name, tuple(round(v, 3) for v in o.matrix_world.translation)) for o in bpy.data.objects if o.type == "EMPTY"])
    print(" IMGS", sorted((i.name, tuple(i.size)) for i in bpy.data.images))
    pl = [o for o in bpy.data.objects if o.name.startswith("Plume_")]
    print(" PLUMES", len(pl), "verts", sum(len(o.data.vertices) for o in pl), "tris", sum(len(o.data.polygons) for o in pl))
    print(" TOTAL verts", sum(len(o.data.vertices) for o in bpy.data.objects if o.type == "MESH"))
