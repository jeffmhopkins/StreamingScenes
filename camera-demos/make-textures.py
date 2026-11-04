from PIL import Image, ImageDraw, ImageFont
import random
F="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def card(name, label, bg, fg, w=512, h=640):
    im=Image.new("RGBA",(w,h),bg); d=ImageDraw.Draw(im)
    for x in range(0,w,32): d.line([(x,0),(x,h)],fill=fg+(70,),width=2)
    for y in range(0,h,32): d.line([(0,y),(w,y)],fill=fg+(70,),width=2)
    d.rectangle([8,8,w-9,h-9],outline=fg+(255,),width=10)
    f=ImageFont.truetype(F,120); bb=d.textbbox((0,0),label,font=f)
    d.text(((w-bb[2])/2,(h-bb[3])/2-40),label,font=f,fill=fg+(255,))
    f2=ImageFont.truetype(F,34); s="the quick brown fox"; bb=d.textbbox((0,0),s,font=f2)
    d.text(((w-bb[2])/2,h-120),s,font=f2,fill=fg+(255,))
    im.save(name+".png")
card("near","NEAR",(200,60,50),(255,235,200))
card("mid","MID",(40,120,200),(230,245,255))
card("far","FAR",(60,160,90),(235,255,230))
# back wall: brick + lights
w,h=1024,640; im=Image.new("RGBA",(w,h),(35,30,45,255)); d=ImageDraw.Draw(im)
for r,y in enumerate(range(0,h,40)):
    off=0 if r%2==0 else 40
    for x in range(-off,w,80): d.rectangle([x+2,y+2,x+78,y+38],fill=(70+random.randint(0,25),45,55,255))
random.seed(3)
for i in range(60):
    x,y=random.randint(0,w),random.randint(0,h); c=random.choice([(255,220,140),(140,200,255),(255,140,200)])
    d.ellipse([x-5,y-5,x+5,y+5],fill=c+(255,))
im.save("wall.png")
# floor: checker
w,h=512,1024; im=Image.new("RGBA",(w,h)); d=ImageDraw.Draw(im)
for i in range(0,w,64):
    for j in range(0,h,64):
        d.rectangle([i,j,i+63,j+63],fill=(210,210,200,255) if (i//64+j//64)%2==0 else (60,60,70,255))
im.save("floor.png")
for n in ["near","mid","far","wall","floor"]:
    im=Image.open(n+".png").convert("RGBA"); open(n+".rgba","wb").write(im.tobytes()); print(n, im.size)
