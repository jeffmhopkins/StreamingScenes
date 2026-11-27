import bpy, bmesh, sys, json
from mathutils import Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath="/workspace/3d-output/spaceship_r14b.glb")
sp=bpy.data.objects["Spaceship"]; print("ROOT", sp.matrix_world)
def parts(obname):
    o=bpy.data.objects[obname]; bm=bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.faces.ensure_lookup_table(); seen=set(); res=[]
    for f in bm.faces:
        if f.index in seen: continue
        stack=[f]; comp=[]; seen.add(f.index)
        while stack:
            g=stack.pop(); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); stack.append(h)
        vs={v for g in comp for v in g.verts}
        mn=Vector([min(v.co[i] for v in vs) for i in range(3)]); mx=Vector([max(v.co[i] for v in vs) for i in range(3)])
        nsum=Vector(); 
        for g in comp: nsum+=g.normal*g.calc_area()
        res.append(dict(n=len(comp),nv=len(vs),c=[round(x,3) for x in (mn+mx)/2],size=[round(x,3) for x in mx-mn],nrm=[round(x,2) for x in nsum.normalized()] if nsum.length>1e-9 else None, mat=sorted({o.data.materials[g.material_index].name for g in comp})))
    return res
for name in ("Ship_EngineGlow","Ship_EngineGlowAft","Ship_AmberLight","Ship_NavGreen","Ship_NavRed","Ship_NavWhite","Ship_CabinLight"):
    for p in parts(name): print(name, p)
gm=parts("Ship_GunMetal")
print("GUN parts", len(gm))
for p in gm:
    if max(p['size'])<0.15: print("GUNSMALL", p)
