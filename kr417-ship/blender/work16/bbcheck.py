import bpy, sys, numpy as np
for p in sys.argv[sys.argv.index("--")+1:]:
    bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=p)
    P=np.array([(o.matrix_world@v.co)[:] for o in bpy.data.objects if o.type=="MESH" for v in o.data.vertices]); print("BB",p.split('/')[-1],P.min(0).round(4),P.max(0).round(4))
