import bpy, json, math
from mathutils import Vector
OUT="/workspace/3d-output"; W=f"{OUT}/work16"
G=json.load(open(f"{W}/rcs_groups.json"))["groups"]; rep={n["name"]:n for n in json.load(open(f"{OUT}/r15_report.json"))["nozzles"]}
VIEWS={"pitch":((0,22,1.5),"side view from port (nose right)"),"yaw":((0.01,0,26),"top view (nose right, port up)"),"roll":((-24,0,1.0),"rear view (looking forward)")}
for g,names in G.items():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=f"{OUT}/spaceship_r15_ship_2k_c.glb")
    bpy.ops.import_scene.gltf(filepath=f"{OUT}/rcs_{g}.glb")
    for m in bpy.data.materials:
        if m.name.startswith(("kr_engine_glow","kr_thruster_glow","kr_pod_glow","Lights_Interior")) and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type=="BSDF_PRINCIPLED": n.inputs["Emission Strength"].default_value=0.0
    hot=bpy.data.materials.new("hot"); hot.use_nodes=True; b=hot.node_tree.nodes["Principled BSDF"]; b.inputs["Emission Color"].default_value=(0.3,0.8,1,1); b.inputs["Emission Strength"].default_value=25
    for nm in names:
        n=rep[nm]; p=Vector(n["exit_blender"]); d=Vector(n["dir_blender"]).normalized()
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16,location=p); bpy.context.object.data.materials.append(hot)
        L=1.6; bpy.ops.mesh.primitive_cone_add(radius1=0.18,radius2=0.02,depth=L,location=p+d*(L/2)); c=bpy.context.object
        c.rotation_euler=d.to_track_quat('Z','Y').to_euler(); c.data.materials.append(hot)
    ax=g.split("_")[0]; loc,desc=VIEWS[ax]
    cam=bpy.data.objects.new("cam",bpy.data.cameras.new("cam")); bpy.context.scene.collection.objects.link(cam); cam.location=loc
    cam.rotation_euler=(Vector((0,0,0.5))-Vector(loc)).to_track_quat('-Z','Y' if ax!="yaw" else 'X').to_euler(); cam.data.lens=50
    if ax=="yaw": cam.rotation_euler=(0,0,math.radians(0))  # straight down; x right? set below
    bpy.context.scene.camera=cam
    if ax=="yaw":
        cam.rotation_euler=(0,0,0)  # looking -Z, image x = world X (nose right), image y = world Y (port up)
    sun=bpy.data.objects.new("sun",bpy.data.lights.new("sun","SUN")); sun.data.energy=3; sun.rotation_euler=(0.6,0.3,0.8); bpy.context.scene.collection.objects.link(sun)
    w=bpy.data.worlds.new("w"); w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0.02,0.025,0.04,1); bpy.context.scene.world=w
    sc=bpy.context.scene; sc.render.engine="CYCLES"; sc.cycles.device="CPU"; sc.cycles.samples=24; sc.render.resolution_x=640; sc.render.resolution_y=400
    sc.render.filepath=f"{W}/rcs_renders/{g}.png"; bpy.ops.render.render(write_still=True); print("RENDERED",g,desc)
