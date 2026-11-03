# Specific reflection masks (round 4), from the keyed cockpit:
#  m-ledge, m-sill, m-seat: the few smooth surfaces that face the windows and mirror them (the ledge
#             under the monitors, the side sills, the seat bolsters), with a fresnel ramp
#  m-edge:    the bevels of the window frames, which catch light bleeding from the glass
#  m-glass:   the glass itself, which faintly mirrors the lit interior (monitors, holograms)
import sys,numpy as np
from scipy import ndimage as nd
from PIL import Image,ImageDraw
D=sys.argv[1] if len(sys.argv)>1 else 'pages'
im=np.asarray(Image.open(f'{D}/cockpit.png')).astype(np.float32)/255
rgb,a=im[...,:3],im[...,3];H,W=a.shape;yy,xx=np.mgrid[0:H,0:W]
win=np.asarray(Image.open(f'{D}/m-window.png')).astype(np.float32)/255
lum=rgb@np.array([.3,.59,.11],np.float32)
m=nd.uniform_filter(lum,7);v=np.sqrt(np.clip(nd.uniform_filter(lum*lum,7)-m*m,0,None))
smooth=np.clip(1-v/.06,0,1)
sat=rgb.max(-1)-rgb.min(-1);light=np.clip((lum-.28)/.25,0,1)*np.clip((sat-.15)/.2,0,1)
def poly(pts,k,blur=6):
  c=Image.new('L',(W,H),0);ImageDraw.Draw(c).polygon(pts,fill=255);return nd.gaussian_filter(np.asarray(c,np.float32)/255,blur)*k
base=a*(1-light)*(.35+.65*smooth)*np.clip(1.2-lum*2.5,0,1)
def surf(name,parts,top):
  reg=np.maximum.reduce(parts)
  fres=np.clip(1-(yy-top)/260,.4,1)  # strongest at the surface's far edge, nearest the glass
  c=nd.gaussian_filter(reg*fres*base,1)
  c=np.clip(c/max(np.percentile(c[c>.02],90),1e-3),0,1)   # full strength on the surface itself
  Image.fromarray((c*255).astype(np.uint8),'L').save(f'{D}/m-{name}.png');return c
surf('ledge',[poly([(480,698),(1530,698),(1530,722),(480,722)],1.0,3),poly([(560,722),(1360,722),(1360,800),(560,800)],.22)],698)
surf('sill',[poly([(0,700),(470,628),(600,690),(600,720),(0,820)],.7),poly([(1920,700),(1450,628),(1320,690),(1320,720),(1920,820)],.7)],640)
con=surf('seat',[poly([(400,990),(600,960),(600,1080),(380,1080)],.8),poly([(1320,960),(1520,990),(1540,1080),(1320,1080)],.8)],960)

# frame bevels: opaque pixels 2-16 px from the glass, brightest right at the edge
dist=nd.distance_transform_edt(win<.5)
edge=np.clip(1-(dist-2)/14,0,1)*(dist>1)*a*(1-light)
Image.fromarray((np.clip(edge,0,1)*255).astype(np.uint8),'L').save(f'{D}/m-edge.png')
# glass: the windows, stronger low and toward the sides (fresnel), with faint smudges
smudge=nd.gaussian_filter(np.random.default_rng(3).random((H,W)).astype(np.float32),40);smudge=(smudge-smudge.mean())/smudge.std()
gl=win*np.clip(.25+.75*np.clip((yy-120)/380,0,None)**1.5+.5*np.abs(xx-960)/960,0,1)*np.clip(1+.1*smudge,0,1.4)
Image.fromarray((np.clip(gl/1.2,0,1)*255).astype(np.uint8),'L').save(f'{D}/m-glass.png')
print(con.mean(),edge.mean(),gl.mean())
