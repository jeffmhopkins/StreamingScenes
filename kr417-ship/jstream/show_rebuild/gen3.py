import json, math
def eio(t): return 4*t**3 if t<0.5 else 1-(-2*t+2)**3/2
L=68600
YAW=(4000,8500); O1=(10000,21500); O2=(21500,33000); O3=(36000,63600); OUT=(63600,68600)
def seg(ms,a,b): return 0.0 if ms<=a else 1.0 if ms>=b else eio((ms-a)/(b-a))
def intro(ms):
    if ms<OUT[0]: return seg(ms,0,5000)
    return 1-seg(ms,*OUT)
def yaw(ms):
    if ms<OUT[0]: return seg(ms,*YAW)
    return 1-seg(ms,*OUT)
def orbit_total(ms): return seg(ms,*O1)+seg(ms,*O2)+seg(ms,*O3)
R=2800.0; RT=1500.0; TURN=30.0
def cam(ms):
    i=intro(ms); o=orbit_total(ms); y=yaw(ms)
    th=35*(1-i)-360*o
    ph=math.radians(-th+TURN*y)
    D=1700+400*(1-i); Tz=-1400*i
    return (D*math.sin(ph), D*math.cos(ph), Tz*math.sin(ph), Tz*math.cos(ph))
times=set([0,4000,5000,8500,10000,21500,33000,36000,63600,L])
for a,b,st in [(0,10000,300),(10000,33000,250),(36000,63600,300),(63600,L,250)]:
    t=a
    while t<=b: times.add(t); t+=st
times=sorted(times)
lanes={k:[] for k in ('ws_cpx','ws_cpz','ws_ctx','ws_ctz')}
for t in times:
    px,pz,tx,tz=cam(t)
    for k,v,r in (('ws_cpx',px,R),('ws_cpz',pz,R),('ws_ctx',tx,RT),('ws_ctz',tz,RT)):
        lanes[k].append({"at_ms":t,"value":round((v+r)/(2*r),6),"curve":"linear" if t>0 else "hold"})
P=lambda t,v,c=None: dict(at_ms=t,value=v,**({"curve":c} if c else {}))
E_,I,O,H="ease_in_out","ease_in","ease_out","hold"
ctl=[
 ("ws_intro",[P(0,0.0,H),P(5000,1.0,E_),P(63600,1.0),P(L,0.0,E_)]),
 ("ws_yaw",[P(0,0.0,H),P(4000,0.0,H),P(8500,1.0,E_),P(63600,1.0),P(L,0.0,E_)]),
 ("ws_skyturn",[P(0,0.0,H),P(7000,0.0,H),P(9500,1.0,E_),P(63600,1.0),P(L,0.0,E_)]),
 ("ws_warp",[P(0,0.0,H),P(6500,0.0,H),P(9500,0.5,E_),P(18700,0.5),P(21500,1.0,E_),P(33000,1.0),P(35500,0.0,O),P(L,0.0)]),
 ("ws_sunfade",[P(0,0.0,H),P(6500,0.0,H),P(9500,1.0,E_),P(33000,1.0),P(35500,0.0,O),P(L,0.0)]),
 ("ws_shake",[P(0,0.0,H),P(6500,0.0,H),P(8100,0.5,I),P(9500,0.5),P(11000,0.25,O),
   P(18700,0.25),P(19300,1.0,I),P(21500,1.0),P(23000,0.5,O),
   P(33000,0.5),P(34600,0.5),P(36000,0.0,O),P(L,0.0)]),
 ("ws_orbit",[P(0,0.0,H),P(10000,0.0,H),P(21500,1.0,E_),P(21501,0.0,H),P(33000,1.0,E_),P(36000,0.0,H),P(63600,1.0,E_),P(L,1.0)]),
]
tl={"timeline_id":"ws_show","name":"KR-417 warp show","duration_ms":L,"loop":"loop","cues":[],
    "lanes":[{"target":{"channel":k},"points":p} for k,p in ctl]+[{"target":{"channel":k},"points":v} for k,v in lanes.items()]}
tlop={"type":"timeline.set","scene_id":"ship_warp_show","timeline":tl}
json.dump({"op":tlop},open('timeline8.json','w'))
print("cam points",len(times))
print("O1 deg done at 18700: %.1f"%(seg(18700,*O1)*360), " yaw deg done at 6500: %.1f"%(seg(6500,*YAW)*30))
show={"show_id":"kr417_warp_show","name":"KR-417 warp show","preset_id":"cut","end":{"type":"loop"},
 "program":[{"clip_id":"c_ship","scene_id":"ship_warp_show","length_ms":L}],
 "sequences":[{"track_id":"s1","name":"Show timeline","cues":[{"cue_id":"q_play","at_ms":0,"action":{"type":"timeline.play","timeline_id":"ws_show"}}]}],
 "bookmarks":[{"bookmark_id":"b_start","at_ms":0,"name":"Start","pausing":False}]}
SHIP_SIGN=1; SKY_SIGN=1
import sys
if len(sys.argv)>2: SHIP_SIGN=int(sys.argv[1]); SKY_SIGN=int(sys.argv[2])
ship_m=[{"channel_id":"ws_warp","clock":"engine","curve":"linear","from":0.0,"kind":"channel","modifier_id":"engine_spool","property":"source","smoothing_ms":60,"source":{"material":"Lights_Interior","param":"emissive_strength"},"to":3.0},
 {"channel_id":"ws_yaw","clock":"engine","curve":"linear","from":0.0,"kind":"channel","modifier_id":"heading_turn","property":"turn","smoothing_ms":0,"to":SHIP_SIGN*TURN}]
sky_m=[{"channel_id":"ws_warp","clock":"engine","curve":"linear","from":0.0,"kind":"channel","modifier_id":"warp","property":"source","smoothing_ms":30,"source":{"param":"warp"},"to":1.0},
 {"channel_id":"ws_skyturn","clock":"engine","curve":"linear","from":0.0,"kind":"channel","modifier_id":"warp_heading","property":"turn","smoothing_ms":0,"to":SKY_SIGN*TURN}]
edits=[{"type":"channel.set","channel":{"channel_id":"ws_yaw","name":"Ship heading turn"}},
 {"type":"channel.set","channel":{"channel_id":"ws_skyturn","name":"Warp heading (sky turn)"}},
 tlop,{"type":"show.set","show":show},
 {"type":"item.set_motion","scene_id":"ship_warp_show","item_id":"sw_ship","motion":ship_m},
 {"type":"item.set_motion","scene_id":"ship_warp_show","item_id":"sw_sky","motion":sky_m}]
json.dump({"edits":edits},open('batch_turn30.json','w'))
json.dump({"edits":edits[4:]},open('batch_turn30_motion.json','w'))
