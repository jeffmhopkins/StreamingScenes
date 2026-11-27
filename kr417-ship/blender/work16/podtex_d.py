import json,struct,io
from PIL import Image
P='/workspace/3d-output/spaceship_r15_ship_2k_d.glb'
b=open(P,'rb').read(); jl,=struct.unpack('<I',b[12:16]); js=json.loads(b[20:20+jl])
bo=20+jl; bl,=struct.unpack('<I',b[bo:bo+4]); binc=bytearray(b[bo+8:bo+8+bl])
buf=io.BytesIO(); Image.new('RGB',(4,4),(255,255,255)).save(buf,'PNG'); data=buf.getvalue()
while len(binc)%4: binc.append(0)
off=len(binc); binc+=data
while len(binc)%4: binc.append(0)
js['buffers'][0]['byteLength']=len(binc)
js['bufferViews'].append({"buffer":0,"byteOffset":off,"byteLength":len(data)})
js['images'].append({"name":"pod_white","mimeType":"image/png","bufferView":len(js['bufferViews'])-1})
js['textures'].append({"source":len(js['images'])-1}); ti=len(js['textures'])-1
for m in js['materials']:
    if m['name']=='kr_pod_glow': m['emissiveTexture']={"index":ti}
j=json.dumps(js,separators=(',',':')).encode(); j+=b' '*((4-len(j)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(j)+8+len(binc))+struct.pack('<I',len(j))+b'JSON'+j+struct.pack('<I',len(binc))+b'BIN\x00'+bytes(binc)
open(P,'wb').write(out); print('ok')
