import json,struct,sys
sys.path.insert(0,'work15')
def rd(p):
    b=open(p,'rb').read(); jl,=struct.unpack('<I',b[12:16]); return json.loads(b[20:20+jl]), b[20+jl:]
def wr(p,js,rest):
    j=json.dumps(js,separators=(',',':')).encode(); j+=b' '*((4-len(j)%4)%4)
    open(p,'wb').write(b'glTF'+struct.pack('<II',2,12+8+len(j)+len(rest))+struct.pack('<I',len(j))+b'JSON'+j+rest)
for p in sys.argv[1:]:
    js,rest=rd(p)
    for m in js['materials']:
        if m['name']=='kr_occluder':
            m['pbrMetallicRoughness']={'baseColorFactor':[0,0,0,1],'metallicFactor':0,'roughnessFactor':1}
            m.pop('emissiveFactor',None); m['extensions']={'KHR_materials_unlit':{}}; m['doubleSided']=True; m.pop('alphaMode',None)
        if m['name'] in ('kr_engine_plume','kr_thruster_plume'):
            m['pbrMetallicRoughness']['baseColorFactor']=[0,0,0,1]; m.setdefault('extensions',{})['KHR_materials_unlit']={}; m['doubleSided']=True
    eu=js.setdefault('extensionsUsed',[]); 'KHR_materials_unlit' in eu or eu.append('KHR_materials_unlit')
    wr(p,js,rest)
    print(p.split('/')[-1],[(m['name'],m.get('alphaMode','OPAQUE'),m.get('emissiveFactor'),list(m.get('extensions',{}))) for m in js['materials']])
