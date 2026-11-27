import bpy
bpy.ops.wm.open_mainfile(filepath="/workspace/3d-output/spaceship_r15.blend")
print("VER", bpy.app.version_string)
for o in bpy.data.objects:
    if o.type=="MESH" and (o.name.startswith(("Plume_RCS","RCSGlow")) ): print("OBJ",o.name,len(o.data.vertices),[m.name for m in o.data.materials])
m=bpy.data.materials["kr_thruster_glow"]; print("TG nodes",[n.type for n in m.node_tree.nodes])
