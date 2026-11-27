# post-export: plume materials -> black base colour (only the emissive is drawn) + KHR_materials_unlit; report materials/textures
import json, struct, sys
def rd(p):
    b = open(p, "rb").read(); assert b[:4] == b"glTF"
    jl, = struct.unpack("<I", b[12:16]); js = json.loads(b[20:20 + jl]); rest = b[20 + jl:]
    return js, rest
def wr(p, js, rest):
    j = json.dumps(js, separators=(",", ":")).encode(); j += b" " * ((4 - len(j) % 4) % 4)
    total = 12 + 8 + len(j) + len(rest)
    open(p, "wb").write(b"glTF" + struct.pack("<II", 2, total) + struct.pack("<I", len(j)) + b"JSON" + j + rest)
for p in sys.argv[1:]:
    js, rest = rd(p)
    for m in js["materials"]:
        if m["name"] in ("kr_engine_plume", "kr_thruster_plume"):
            m["pbrMetallicRoughness"]["baseColorFactor"] = [0, 0, 0, 1]
            m.setdefault("extensions", {})["KHR_materials_unlit"] = {}
            m["doubleSided"] = True; assert m.get("alphaMode") == "BLEND", m
    eu = js.setdefault("extensionsUsed", [])
    if "KHR_materials_unlit" not in eu: eu.append("KHR_materials_unlit")
    wr(p, js, rest)
    print(p, [ (m["name"], m.get("alphaMode","OPAQUE"), m.get("doubleSided",False), m.get("emissiveFactor"), m.get("extensions")) for m in js["materials"]])
    print("extensionsUsed", js.get("extensionsUsed"), "required", js.get("extensionsRequired"))
    print("images", [(i.get("name"), i.get("mimeType")) for i in js["images"]], "textures", len(js["textures"]))
