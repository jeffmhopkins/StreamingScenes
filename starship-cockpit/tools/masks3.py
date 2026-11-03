# Reflection masks from the plate's own lighting (round 5). The cockpit plate was lit
# from the windows, so a surface that already catches that light faces the glass and is
# where a reflection belongs: its lit faces (soft sheen) and its specular lips (sharp).
# Each mirror's mask is that gloss inside a soft band for the surfaces it mirrors onto
# (the console under the monitors, the side sills, the seat bolsters), so a reflection
# follows the real edges and panels instead of a drawn shape.
import sys,numpy as np
from scipy import ndimage as nd
from PIL import Image
D=sys.argv[1] if len(sys.argv)>1 else 'pages'
im=np.asarray(Image.open(f'{D}/cockpit.png')).astype(np.float32)/255
rgb,a=im[...,:3],im[...,3];H,W=a.shape;yy,xx=np.mgrid[0:H,0:W].astype(np.float32)
lum=rgb@np.array([.3,.59,.11],np.float32)
warm=np.clip((rgb[...,0]-rgb[...,2])*4,0,1)            # amber lights and their glow
cool=(1-warm)*a
spec=np.clip(np.clip(lum-nd.gaussian_filter(lum,8),0,None)*8,0,1)*cool
face=np.clip((lum-.06)/.15,0,1)*cool
gloss=np.clip(.45*face+spec,0,1)
def band(x0,x1,y0,y1,soft=40):
  m=((xx>=x0)&(xx<=x1)&(yy>=y0)&(yy<=y1)).astype(np.float32);return nd.gaussian_filter(m,soft)
def save(name,band_,top):
  fres=np.clip(1-(yy-top)/320,.35,1)                   # surfaces nearest the glass mirror most
  m=gloss*band_*fres;m=np.clip(m/max(np.percentile(m[m>.02],95),1e-3),0,1)
  Image.fromarray((m*255).astype(np.uint8),'L').save(f'{D}/m-{name}.png');return m
save('ledge',band(430,1490,700,860),700)
save('sill',np.maximum(band(-100,560,560,900),band(1360,2020,560,900)),600)
save('seat',np.maximum(band(390,600,945,1120,18),band(1430,1630,945,1120,18)),940)
