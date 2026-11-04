"""Builds the small studio the UI captures show, in a running JStream daemon over MCP:
three scenes of starship-cockpit stills, with a title, and Bridge on program. JS_TOKEN
names the daemon's token file and JS_MCP its endpoint, as for ../starship-cockpit/jstream/mcp.py."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "starship-cockpit", "jstream"))
import mcp
from mcp import batch, asset, geo, init
init()
M=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "starship-cockpit", "media")
def img(sid,name,f): return {"type":"source.create","source_id":sid,"name":name,"kind":{"type":"builtin","kind":"image"},"settings":{"file":asset(f"{M}/{f}")}}
def add(sc,it,src,g): return {"type":"item.add","scene_id":sc,"item_id":it,"source_id":src,"geometry":g}
e=[{"type":"canvas.set_size","width":1920,"height":1080},
 {"type":"scene.create","scene_id":"bridge","name":"Bridge"},
 {"type":"scene.create","scene_id":"nebula","name":"Nebula flyby"},
 {"type":"scene.create","scene_id":"brb","name":"Be right back"},
 img("hyper","Hyperspace","hyperspace.jpg"), img("mons","Monitors","monitors.jpg"),
 img("tyr","Tyr VII","tyr-vii.jpg"), img("neb","Nebula","nebula.jpg"),
 {"type":"source.create","source_id":"title","name":"Title","kind":{"type":"builtin","kind":"text"},"settings":{"text":"STARSHIP STREAM · LIVE","size":64}},
 add("bridge","bg","hyper",geo(0,0,1920,1080)),
 add("bridge","cam","mons",geo(1180,620,640,360)),
 add("bridge","tt","title",geo(80,60,900,90)),
 add("nebula","nb","neb",geo(0,0,1920,1080)),
 add("nebula","planet","tyr",geo(1100,180,700,394)),
 add("brb","bb","tyr",geo(0,0,1920,1080)),
]
print(batch([x for x in e if x]))
print(mcp.op({"type":"scene.switch","scene_id":"bridge"}))
