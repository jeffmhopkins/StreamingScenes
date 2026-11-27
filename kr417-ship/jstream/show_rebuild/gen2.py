import json, math
def eio(t): return 4*t**3 if t<0.5 else 1-(-2*t+2)**3/2
L=64500
# beats
INTRO=(0,5000); W1=(2400,5400); O1=(5900,17400); W2=(14600,17400); O2=(17400,28900)
DROP=(28900,31400); O3=(31900,59500); OUT=(59500,64500)
def intro(ms):
    if ms<=0: return 0.0
    if ms<5000: return eio(ms/5000)
    if ms<=OUT[0]: return 1.0
    if ms<L: return 1-eio((ms-OUT[0])/5000)
    return 0.0
def seg(ms,a,b):
    return 0.0 if ms<=a else 1.0 if ms>=b else eio((ms-a)/(b-a))
def orbit_total(ms): return seg(ms,*O1)+seg(ms,*O2)+seg(ms,*O3)
R=2800.0; RT=1500.0
def cam(ms):
    i=intro(ms); o=orbit_total(ms)
    th=35*(1-i)-360*o; ph=math.radians(-th)
    D=1700+400*(1-i); Tz=-1400*i
    return (D*math.sin(ph), D*math.cos(ph), Tz*math.sin(ph), Tz*math.cos(ph))
times=set([0,5000,5900,17400,28900,31900,59500,64500])
for a,b,st in [(0,5000,250),(5900,28900,250),(31900,59500,300),(59500,64500,250)]:
    t=a
    while t<=b: times.add(t); t+=st
times=sorted(times)
lanes={k:[] for k in ('ws_cpx','ws_cpz','ws_ctx','ws_ctz')}
for t in times:
    px,pz,tx,tz=cam(t)
    for k,v,r in (('ws_cpx',px,R),('ws_cpz',pz,R),('ws_ctx',tx,RT),('ws_ctz',tz,RT)):
        lanes[k].append({"at_ms":t,"value":round((v+r)/(2*r),6),"curve":"linear" if t>0 else "hold"})
P=lambda t,v,c=None: dict(at_ms=t,value=v,**({"curve":c} if c else {}))
ctl=[
 {"target":{"channel":"ws_intro"},"points":[P(0,0.0,"hold"),P(5000,1.0,"ease_in_out"),P(59500,1.0),P(L,0.0,"ease_in_out")]},
 {"target":{"channel":"ws_warp"},"points":[P(0,0.0,"hold"),P(2400,0.0,"hold"),P(5400,0.5,"ease_in_out"),P(14600,0.5),P(17400,1.0,"ease_in_out"),P(28900,1.0),P(31400,0.0,"ease_out"),P(L,0.0)]},
 {"target":{"channel":"ws_shake"},"points":[P(0,0.0,"hold"),P(2400,0.0,"hold"),P(4000,0.5,"ease_in"),P(5400,0.5),P(6900,0.0,"ease_out"),
   P(14600,0.0,"hold"),P(15200,1.0,"ease_in"),P(17400,1.0),P(18900,0.0,"ease_out"),
   P(28900,0.0,"hold"),P(29700,0.5,"ease_in"),P(30500,0.5),P(31900,0.0,"ease_out"),P(L,0.0)]},
 {"target":{"channel":"ws_orbit"},"points":[P(0,0.0,"hold"),P(5900,0.0,"hold"),P(17400,1.0,"ease_in_out"),P(17401,0.0,"hold"),P(28900,1.0,"ease_in_out"),P(31900,0.0,"hold"),P(59500,1.0,"ease_in_out"),P(L,1.0)]},
]
tl={"timeline_id":"ws_show","name":"KR-417 warp show","duration_ms":L,"loop":"loop","cues":[],"lanes":ctl+[{"target":{"channel":k},"points":v} for k,v in lanes.items()]}
json.dump({"op":{"type":"timeline.set","scene_id":"ship_warp_show","timeline":tl}},open('timeline6.json','w'))
print("points",len(times), max(len(l["points"]) for l in tl["lanes"]))
# check: angle 20deg before end of O1 at W2 start
o=seg(14600,*O1); print("orbit1 at 14600: %.1f deg done"%(o*360))
