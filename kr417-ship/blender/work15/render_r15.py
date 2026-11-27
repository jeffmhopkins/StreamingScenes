import bpy, math, sys
from mathutils import Vector, Quaternion
argv = sys.argv[sys.argv.index("--") + 1:]
GLB = argv[0]; MODE = argv[1]; ONLY = argv[2].split(",") if len(argv) > 2 and argv[2] else []
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 40; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 1200, 675
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
sc.cycles.transparent_max_bounces = 64; sc.cycles.max_bounces = 4
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True; nt = w.node_tree
bg = nt.nodes["Background"]; bg.inputs[0].default_value = (0.012, 0.013, 0.016, 1)
bgc = nt.nodes.new("ShaderNodeBackground"); bgc.inputs[0].default_value = (0, 0, 0, 1)
lp = nt.nodes.new("ShaderNodeLightPath"); mx = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs[0]); nt.links.new(bg.outputs[0], mx.inputs[1]); nt.links.new(bgc.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], nt.nodes["World Output"].inputs[0])
sun = bpy.data.lights.new("Sun", "SUN"); sun.energy = 4.0 if MODE == "normal" else 1.2; sun.angle = 0.02; sun.color = (1, 0.95, 0.88)
so = bpy.data.objects.new("Sun", sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(50), 0, math.radians(150))
fl = bpy.data.lights.new("Fill", "SUN"); fl.energy = 0.5; fl.color = (0.6, 0.7, 1.0)
fo = bpy.data.objects.new("Fill", fl); sc.collection.objects.link(fo); fo.rotation_euler = (math.radians(120), 0, math.radians(-40))
# rebuild unlit plume materials as JStream draws them: emitted = emissiveTex * strength, blended by base alpha, base rgb black
for m in bpy.data.materials:
    if m.name.startswith("kr_") and m.name.endswith("_plume"):
        img = next(n.image for n in m.node_tree.nodes if n.type == "TEX_IMAGE")
        nt2 = m.node_tree; nt2.nodes.clear(); L = nt2.links.new
        out = nt2.nodes.new("ShaderNodeOutputMaterial"); tx = nt2.nodes.new("ShaderNodeTexImage"); tx.image = img; tx.extension = "EXTEND"
        uv = nt2.nodes.new("ShaderNodeUVMap"); L(uv.outputs[0], tx.inputs[0])
        em = nt2.nodes.new("ShaderNodeEmission"); L(tx.outputs["Color"], em.inputs[0]); em.inputs[1].default_value = 6.0 if MODE == "normal" else 0.0
        tr = nt2.nodes.new("ShaderNodeBsdfTransparent"); mix = nt2.nodes.new("ShaderNodeMixShader")
        L(tx.outputs["Alpha"], mix.inputs[0]); L(tr.outputs[0], mix.inputs[1]); L(em.outputs[0], mix.inputs[2]); L(mix.outputs[0], out.inputs[0])
        m.blend_method = "BLEND"
    if MODE == "warp" and m.name in ("kr_engine_glow", "kr_thruster_glow"):
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
    if MODE == "warp" and m.name == "kr_pod_glow":
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 18.0
if MODE == "warp":   # the blue point lights JStream would place at pod_L / pod_R
    for e in ("pod_L", "pod_R"):
        pl = bpy.data.lights.new(e + "_light", "POINT"); pl.energy = 60; pl.color = (0.37, 0.66, 1.0); pl.shadow_soft_size = 0.1
        po = bpy.data.objects.new(e + "_light", pl); sc.collection.objects.link(po); po.location = bpy.data.objects[e].matrix_world.translation
cd = bpy.data.cameras.new("Cam"); cam = bpy.data.objects.new("Cam", cd); sc.collection.objects.link(cam); sc.camera = cam; cd.clip_start = 0.05
def place(yaw, pitch, dist, lens, t=(0, 0, 0)):
    cd.lens = lens; t = Vector(t); y, p = math.radians(yaw), math.radians(pitch)
    cam.location = t + dist * Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), math.sin(p)))
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
V = {
 "rear": (-90, 6, 26, 60, (-2.5, 0, 0.3)), "rear34": (-130, 18, 26, 60, (-2.0, 0, 0.2)), "side": (0, 4, 30, 60, (-2.0, 0, 0.2)),
 "top": (0, 89.5, 32, 60, (-2.0, 0, 0)), "front34": (40, 10, 30, 60, (-1.5, 0, 0.3)), "below": (0, -89.5, 32, 60, (-2.0, 0, 0)),
 "below_rear34": (-120, -30, 24, 60, (-3.0, 0, 0)), "close_aft": (-118, 14, 9, 60, (-7.6, 0, 0.4)), "close_wingtip": (-35, 22, 5.0, 60, (-5.0, 4.6, 0.4)),
 "close_nose_rcs": (55, -12, 6.0, 60, (4.6, 0, -0.7)), "close_aftside": (-60, -8, 6.5, 60, (-6.6, 1.2, 0.4)),
}
for n, (yaw, pitch, dist, lens, t) in V.items():
    if ONLY and n not in ONLY: continue
    place(yaw, pitch, dist, lens, t)
    sc.render.filepath = f"/workspace/3d-output/r15_{MODE}_{n}.png"; bpy.ops.render.render(write_still=True)
    print("RENDERED", sc.render.filepath)
