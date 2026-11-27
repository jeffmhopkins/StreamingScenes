import json,struct,sys
def rd(p):
    b=open(p,'rb').read(); jl,=struct.unpack('<I',b[12:16]); js=json.loads(b[20:20+jl]); r=b[20+jl:]
    bl,=struct.unpack('<I',r[:4]); return js, r[8:8+bl]
def wr(p,js,bin_):
    bin_+=b'\0'*((4-len(bin_)%4)%4); js['buffers']=[{'byteLength':len(bin_)}]
    j=json.dumps(js,separators=(',',':')).encode(); j+=b' '*((4-len(j)%4)%4)
    open(p,'wb').write(b'glTF'+struct.pack('<II',2,12+8+len(j)+8+len(bin_))+struct.pack('<I',len(j))+b'JSON'+j+struct.pack('<I',len(bin_))+b'BIN\0'+bin_)
oj,ob=rd('work16/occluder.glb')
for src in sys.argv[1:]:
    js,b=rd(src); b+=b'\0'*((4-len(b)%4)%4); off=len(b); b+=ob
    bv0=len(js['bufferViews']); ac0=len(js['accessors']); mt=len(js['materials'])
    for v in oj['bufferViews']: v=dict(v); v['byteOffset']=v.get('byteOffset',0)+off; v['buffer']=0; js['bufferViews'].append(v)
    for a in oj['accessors']: a=dict(a); a['bufferView']+=bv0; js['accessors'].append(a)
    js['materials'].append({'name':'kr_occluder','pbrMetallicRoughness':{'baseColorFactor':[0,0,0,1],'metallicFactor':0,'roughnessFactor':1},'doubleSided':True,'extensions':{'KHR_materials_unlit':{}}})
    mesh=json.loads(json.dumps(oj['meshes'][0]))
    for pr in mesh['primitives']:
        pr['attributes']={k:v+ac0 for k,v in pr['attributes'].items()}; pr['indices']+=ac0; pr['material']=mt
    js['meshes'].append(mesh); js['nodes'].append({'name':'HullOccluder','mesh':len(js['meshes'])-1})
    js['scenes'][js.get('scene',0)]['nodes'].append(len(js['nodes'])-1)
    eu=js.setdefault('extensionsUsed',[]); 'KHR_materials_unlit' in eu or eu.append('KHR_materials_unlit')
    dst=src.replace('.glb','_occ.glb'); wr(dst,js,b); print(dst, len(js['meshes']))
