import json, math
B=json.load(open('timeline8.json'))['op']   # current 68.6 s timeline
P=lambda t,v,c=None: dict(at_ms=t,value=v,**({"curve":c} if c else {}))
L=68600
B['timeline']['lanes']=[l for l in B['timeline']['lanes'] if l['target']['channel'] not in ('ship_thrusters','ship_warp_pods')]
B['timeline']['lanes'].append({"target":{"channel":"ship_thrusters"},"points":[P(0,1.0,"hold"),P(6500,1.0,"hold"),P(9500,0.0,"ease_in_out"),P(33000,0.0),P(35500,1.0,"ease_out"),P(L,1.0)]})
B['timeline']['lanes'].append({"target":{"channel":"ship_warp_pods"},"points":[P(0,0.0,"hold"),P(6500,0.0,"hold"),P(9500,0.5,"ease_in_out"),P(18700,0.5),P(21500,1.0,"ease_in_out"),P(33000,1.0),P(35500,0.0,"ease_out"),P(L,0.0)]})
json.dump({"op":B},open('timeline9.json','w'))
R=1.2593370534436248
s=1400/14.491; c=(-0.1155,0.54375)  # ship bbox centre glTF x,y
def ch(mid,chan,prop,frm,to,src=None,mode=None,sm=60):
    m={"modifier_id":mid,"kind":"channel","channel_id":chan,"property":prop,"from":frm,"to":to,"curve":"linear","smoothing_ms":sm,"clock":"engine"}
    if src: m["source"]=src
    if mode: m["mode"]=mode
    return m
def osc(mid,prop,amp,period,amount,src=None):
    m={"modifier_id":mid,"kind":"oscillate","property":prop,"amplitude":amp,"period_ms":period,"shape":"sine","clock":"engine","amount":amount}
    if src: m["source"]=src
    return m
yaw=ch("heading_turn","ws_yaw","turn",0.0,30.0,sm=0)
ship_m=[ch("engine_spool","ws_warp","source",0.0,3.0,{"material":"Lights_Interior","param":"emissive_strength"}),yaw,
  ch("thr_engine","ship_thrusters","source",0.0,1.0,{"material":"kr_engine_glow","param":"emissive_strength"},"replace"),
  ch("thr_rcs","ship_thrusters","source",0.0,1.0,{"material":"kr_thruster_glow","param":"emissive_strength"},"replace"),
  ch("pod_glow","ship_warp_pods","source",0.0,1.28,{"material":"kr_pod_glow","param":"emissive_strength"},"replace"),
  osc("pod_pulse","source",0.32,1000,"ship_warp_pods",{"material":"kr_pod_glow","param":"emissive_strength"})]
plume_m=[yaw,
  ch("plume_eng","ship_thrusters","source",0.0,1.0,{"material":"kr_engine_plume","param":"emissive_strength"},"replace"),
  ch("plume_rcs","ship_thrusters","source",0.0,1.0,{"material":"kr_thruster_plume","param":"emissive_strength"},"replace"),
  ch("plume_fade","ship_thrusters","opacity",-1.0,0.0)]
# pod light positions
def pod(zg,th):
    x=(-4.86-c[0])*s; z=zg*s; t=math.radians(th)
    return (x*math.cos(t)+z*math.sin(t), -x*math.sin(t)+z*math.cos(t))
lights=[]
for side,zg in (("L",-5.25),("R",5.25)):
    x0,d0=pod(zg,90); x1,d1=pod(zg,120); y=540+(c[1]-0.4)*s
    geo={"center":{"x":round(960+x0,1),"y":round(y,1)},"depth_px":round(d0,1),"fit_mode":"fit","rotation_deg":0.0,"size":{"width":60.0,"height":60.0},"tilt_deg":0.0,"turn_deg":0.0}
    mot=[ch("pod_light","ship_warp_pods","source",0.0,5.0,{"param":"intensity"},"replace"),
         osc("pod_light_pulse","source",1.25,1000,"ship_warp_pods",{"param":"intensity"}),
         ch("follow_x","ws_yaw","x",0.0,round(x1-x0,1),sm=0), ch("follow_depth","ws_yaw","depth",0.0,round(d1-d0,1),sm=0)]
    lights.append((f"sw_pod_{side}",geo,mot)); print(side,geo["center"],geo["depth_px"],"->",round(x1-x0,1),round(d1-d0,1))
S="ship_warp_show"
E_=[{"type":"channel.set","channel":{"channel_id":"ship_thrusters","name":"Thruster amount","default":1.0}},
 {"type":"channel.set","channel":{"channel_id":"ship_warp_pods","name":"Warp pod glow","default":0.0}},
 {"type":"source.duplicate","source_id":"ship_kr417","new_source_id":"ws_ship_r15","name":"KR-417 r15 ship (warp show)"},
 {"type":"source.set_settings","source_id":"ws_ship_r15","patch":{"file":{"path":"spaceship/spaceship_r15_ship_2k.glb","root":"collection","type":"asset"},"texture_size":"2048"}},
 {"type":"source.duplicate","source_id":"ship_kr417","new_source_id":"ws_plumes","name":"KR-417 r15 engine plumes (warp show)"},
 {"type":"source.set_settings","source_id":"ws_plumes","patch":{"file":{"path":"spaceship/ship_plumes.glb","root":"collection","type":"asset"},"texture_size":"2048","casts_shadows":False,"receives_shadows":False,"reflections":False}},
 {"type":"source.duplicate","source_id":"ws_warp_light","new_source_id":"ws_pod_light","name":"KR-417 warp pod light (warp show)"},
 {"type":"source.set_settings","source_id":"ws_pod_light","patch":{"type":"point","color":"#5fa8ff","intensity":0.0,"range_px":700.0}},
 {"type":"item.set_source","item_id":"sw_ship","source_id":"ws_ship_r15"},
 {"type":"item.set_motion","scene_id":S,"item_id":"sw_ship","motion":ship_m},
 {"type":"item.add","scene_id":S,"item_id":"sw_plumes","source_id":"ws_plumes","geometry":{"center":{"x":960.0,"y":540.0},"depth_px":0.0,"fit_mode":"fit","rotation_deg":0.0,"size":{"width":round(1400*R,2),"height":round(800*R,2)},"tilt_deg":0.0,"turn_deg":90.0}},
 {"type":"item.set_motion","scene_id":S,"item_id":"sw_plumes","motion":plume_m}]
for iid,geo,mot in lights:
    E_+=[{"type":"item.add","scene_id":S,"item_id":iid,"source_id":"ws_pod_light","geometry":geo},{"type":"item.set_motion","scene_id":S,"item_id":iid,"motion":mot}]
E_.append({"type":"filter.add","owner":{"type":"scene","scene_id":S},"chain":"video","filter_id":"ws_bloom","kind":"depth_bloom","settings":{"threshold":2.0,"strength":0.6,"radius_px":18.0,"depth_px":200.0}})
E_.append(B)
json.dump({"edits":E_},open('batch_engines.json','w')); print(len(E_),"edits")
