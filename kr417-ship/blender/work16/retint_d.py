import json,struct,io
from PIL import Image, ImageOps
P='/workspace/3d-output/spaceship_r15_ship_2k_d.glb'
b=open(P,'rb').read(); jl,=struct.unpack('<I',b[12:16]); js=json.loads(b[20:20+jl])
bin_off=20+jl; bl,=struct.unpack('<I',b[bin_off:bin_off+4]); assert b[bin_off+4:bin_off+8]==b'BIN\x00'; binc=bytearray(b[bin_off+8:bin_off+8+bl])
im=Image.open('/workspace/3d-output/work14/tex2k/FX_emissive.jpg').convert('RGB')
g=ImageOps.autocontrast(im.convert('L')).convert('RGB'); buf=io.BytesIO(); g.save(buf,'JPEG',quality=90); data=buf.getvalue()
while len(binc)%4: binc.append(0)
off=len(binc); binc+=data
while len(binc)%4: binc.append(0)
js['buffers'][0]['byteLength']=len(binc)
js['bufferViews'].append({"buffer":0,"byteOffset":off,"byteLength":len(data)}); bv=len(js['bufferViews'])-1
js['images'].append({"name":"FX_emissive_grey","mimeType":"image/jpeg","bufferView":bv}); ii=len(js['images'])-1
fxt=None
for m in js['materials']:
    if m['name']=='kr_engine_glow': fxt=js['textures'][m['emissiveTexture']['index']]
js['textures'].append({k:v for k,v in fxt.items() if k!='source'} | {"source":ii}); ti=len(js['textures'])-1
def lin(c): c/=255; return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
tint=[round(lin(x),4) for x in (0xbf,0xe0,0xff)]
for m in js['materials']:
    if m['name'] in ('kr_engine_glow','kr_thruster_glow','kr_ion_glow'):
        m['emissiveTexture']={"index":ti, **({k:v for k,v in m['emissiveTexture'].items() if k!='index'})}
        m['emissiveFactor']=tint
j=json.dumps(js,separators=(',',':')).encode(); j+=b' '*((4-len(j)%4)%4)
out=b'glTF'+struct.pack('<II',2,12+8+len(j)+8+len(binc))+struct.pack('<I',len(j))+b'JSON'+j+struct.pack('<I',len(binc))+b'BIN\x00'+bytes(binc)
open(P,'wb').write(out); print('ok',len(out),tint)
