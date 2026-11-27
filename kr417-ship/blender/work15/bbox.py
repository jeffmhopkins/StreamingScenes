import bpy
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath="/workspace/3d-output/spaceship_r15.glb")
import numpy as np
def bb(f):
    P=np.array([ (o.matrix_world@v.co)[:] for o in bpy.data.objects if o.type=="MESH" and f(o) for v in o.data.vertices]); return P.min(0).round(3), P.max(0).round(3)
print("SHIP", bb(lambda o: not o.name.startswith(("Plume_","PodGlow","RCSGlow"))))
print("ALL", bb(lambda o: True))
