import json, math, sys
S = float(sys.argv[1]) if len(sys.argv)>1 else 1.0
def eio(t): return 4*t**3 if t<0.5 else 1-(-2*t+2)**3/2
def ei(t): return t**3
def eo(t): return 1-(1-t)**3
def intro(ms):
    if ms<=0: return 0.0
    if ms<5000: return eio(ms/5000)
    if ms<=48000: return 1.0
    if ms<53000: return 1-eio((ms-48000)/5000)
    return 0.0
def orbit(ms):
    if ms<5900: return 0.0
    if ms<17400: return eio((ms-5900)/11500)
    if ms<20400: return 1.0
    if ms<48000: return eio((ms-20400)/27600)
    return 1.0
R=2800.0; RT=1500.0
def cam(ms):
    i=intro(ms); o=orbit(ms)
    th=35*(1-i)-360*o
    ph=math.radians(S*-th)
    D=1700+400*(1-i); Tz=-1400*i
    return (D*math.sin(ph), D*math.cos(ph), Tz*math.sin(ph), Tz*math.cos(ph))
times=set([0,5000,5900,17400,20400,48000,53000])
for a,b,st in [(0,5000,200),(5900,17400,250),(20400,48000,250),(48000,53000,200)]:
    t=a
    while t<=b: times.add(t); t+=st
# orbit jump at 24000: value at 23999 is orbit 1 (=-360) and 24000 is 0 -> same angle; sample just before
times.add(20399)
times=sorted(times)
lanes={k:[] for k in ('ws_cpx','ws_cpz','ws_ctx','ws_ctz')}
for t in times:
    px,pz,tx,tz=cam(t)
    for k,v,r in (('ws_cpx',px,R),('ws_cpz',pz,R),('ws_ctx',tx,RT),('ws_ctz',tz,RT)):
        val=round((v+r)/(2*r),6)
        lanes[k].append({"at_ms":t,"value":val,"curve":"linear" if t>0 else "hold"})
print(len(times), file=sys.stderr)
# existing lanes
old=[{"target":{"channel":"ws_intro"},"points":[{"at_ms":0,"value":0.0,"curve":"hold"},{"at_ms":5000,"value":1.0,"curve":"ease_in_out"},{"at_ms":48000,"value":1.0},{"at_ms":53000,"value":0.0,"curve":"ease_in_out"}]},{"target":{"channel":"ws_warp"},"points":[{"at_ms":0,"value":0.0,"curve":"hold"},{"at_ms":6000,"value":0.0,"curve":"hold"},{"at_ms":9000,"value":1.0,"curve":"ease_in"},{"at_ms":21000,"value":1.0},{"at_ms":23500,"value":0.0,"curve":"ease_out"},{"at_ms":53000,"value":0.0}]},{"target":{"channel":"ws_shake"},"points":[{"at_ms":0,"value":0.0,"curve":"hold"},{"at_ms":6000,"value":0.0,"curve":"hold"},{"at_ms":7800,"value":1.0,"curve":"ease_in"},{"at_ms":8600,"value":1.0},{"at_ms":10000,"value":0.0,"curve":"ease_out"},{"at_ms":21000,"value":0.0,"curve":"hold"},{"at_ms":21800,"value":1.0,"curve":"ease_in"},{"at_ms":22600,"value":1.0},{"at_ms":24000,"value":0.0,"curve":"ease_out"},{"at_ms":53000,"value":0.0}]},{"target":{"channel":"ws_orbit"},"points":[{"at_ms":0,"value":0.0,"curve":"hold"},{"at_ms":9500,"value":0.0,"curve":"hold"},{"at_ms":21000,"value":1.0,"curve":"ease_in_out"},{"at_ms":24000,"value":0.0,"curve":"hold"},{"at_ms":48000,"value":1.0,"curve":"ease_in_out"},{"at_ms":53000,"value":1.0}]}]
tl={"timeline_id":"ws_show","name":"KR-417 warp show","duration_ms":53000,"loop":"loop","cues":[],"lanes":old+[{"target":{"channel":k},"points":v} for k,v in lanes.items()]}
json.dump({"op":{"type":"timeline.set","scene_id":"ship_warp_show","timeline":tl}},open('timeline.json','w'))
# initial channel values at t=0
px,pz,tx,tz=cam(0)
init={'ws_cpx':(px+R)/(2*R),'ws_cpz':(pz+R)/(2*R),'ws_ctx':(tx+RT)/(2*RT),'ws_ctz':(tz+RT)/(2*RT)}
json.dump(init,open('init.json','w'))
cm=[{"modifier_id":"cam_px","property":"position_x","kind":"channel","channel_id":"ws_cpx","smoothing_ms":0,"curve":"linear","from":-R,"to":R,"clock":"engine"},
{"modifier_id":"cam_pz","property":"position_z","kind":"channel","channel_id":"ws_cpz","smoothing_ms":0,"curve":"linear","from":-R,"to":R,"clock":"engine"},
{"modifier_id":"cam_tx","property":"target_x","kind":"channel","channel_id":"ws_ctx","smoothing_ms":0,"curve":"linear","from":-RT,"to":RT,"clock":"engine"},
{"modifier_id":"cam_tz","property":"target_z","kind":"channel","channel_id":"ws_ctz","smoothing_ms":0,"curve":"linear","from":-RT,"to":RT,"clock":"engine"},
{"modifier_id":"intro_dolly_y","property":"position_y","kind":"channel","channel_id":"ws_intro","smoothing_ms":0,"curve":"linear","from":60.0,"to":0.0,"clock":"engine"},
{"modifier_id":"intro_look_y","property":"target_y","kind":"channel","channel_id":"ws_intro","smoothing_ms":0,"curve":"linear","from":-20.0,"to":0.0,"clock":"engine"},
{"modifier_id":"warp_zoom","property":"fov","kind":"channel","channel_id":"ws_warp","smoothing_ms":0,"curve":"linear","from":0.0,"to":-17.0,"clock":"engine"},
{"modifier_id":"shudder_x","property":"position_x","kind":"wiggle","amplitude":14.0,"frequency_hz":9.0,"seed":11,"octaves":2,"clock":"engine","amount":"ws_shake"},
{"modifier_id":"shudder_y","property":"position_y","kind":"wiggle","amplitude":11.0,"frequency_hz":11.0,"seed":23,"octaves":2,"clock":"engine","amount":"ws_shake"},
{"modifier_id":"shudder_roll","property":"roll","kind":"wiggle","amplitude":0.6,"frequency_hz":7.0,"seed":5,"octaves":1,"clock":"engine","amount":"ws_shake"}]
json.dump({"op":{"type":"scene.set_camera_motion","scene_id":"ship_warp_show","motion":cm}},open('cammotion.json','w'))
