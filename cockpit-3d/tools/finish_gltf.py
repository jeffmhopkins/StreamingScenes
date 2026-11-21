"""Wires the texture sets into the glTF that build_cockpit.py exported.

    python finish_gltf.py <cockpit.gltf>

Blender exports the geometry and material names with no images. This rewrites every
material from the table below, so the file names exactly the JPEG and PNG files in
textures/ (no re-encoding, no packing) and uses only what JStream's loader reads:
metallic-roughness with normal, occlusion and emissive maps, KHR_materials_unlit and
KHR_materials_emissive_strength.
"""
import json
import sys

PATH = sys.argv[1]

# Tiling sets: material -> (texture set, base colour factor, metallic, roughness, normal scale)
TILED = {
    "paint": ("paint", [1, 1, 1, 1], 1.0, 1.0, 0.6),
    "paint_dark": ("paint", [0.45, 0.45, 0.47, 1], 1.0, 1.0, 0.6),
    "floor": ("floor", [1, 1, 1, 1], 1.0, 1.0, 1.0),
    "leather": ("leather", [1, 1, 1, 1], 1.0, 1.0, 1.0),
    "plastic": ("plastic", [1, 1, 1, 1], 1.0, 1.0, 0.35),
    "hexpanel": ("hexpanel", [1, 1, 1, 1], 1.0, 1.0, 1.0),
}
SCREENS = ["screen_center", "screen_left", "screen_right", "screen_side_left",
           "screen_side_right", "screen_overhead_left", "screen_overhead_right",
           "screen_desk"]


def main():
    g = json.load(open(PATH))
    g["images"], g["textures"] = [], []
    g["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
    index = {}

    def texture(uri):
        if uri not in index:
            g["images"].append({"uri": f"textures/{uri}",
                                "mimeType": "image/png" if uri.endswith(".png") else "image/jpeg"})
            g["textures"].append({"sampler": 0, "source": len(g["images"]) - 1})
            index[uri] = len(g["textures"]) - 1
        return {"index": index[uri]}

    for m in g["materials"]:
        name = m["name"]
        if name in TILED:
            s, factor, metal, rough, nscale = TILED[name]
            orm = texture(f"{s}-orm.jpg")
            m.clear()
            m.update({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorTexture": texture(f"{s}-color.jpg"),
                    "baseColorFactor": factor,
                    "metallicRoughnessTexture": dict(orm),
                    "metallicFactor": metal,
                    "roughnessFactor": rough,
                },
                "normalTexture": {**texture(f"{s}-normal.jpg"), "scale": nscale},
                "occlusionTexture": {**orm, "strength": 1.0},
                "doubleSided": True,
            })
        elif name in SCREENS:
            # Unlit: whatever source is mapped here shows at its own colours, like a
            # screen, whatever the lighting. `texture_material` = this name replaces it.
            m.clear()
            m.update({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorTexture": texture(f"{name}.jpg"),
                    "baseColorFactor": [1, 1, 1, 1],
                    "metallicFactor": 0,
                    "roughnessFactor": 1,
                },
                "extensions": {"KHR_materials_unlit": {}},
                "doubleSided": False,
            })
        elif name == "decals":
            m.clear()
            m.update({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorTexture": texture("decals.png"),
                    "baseColorFactor": [1, 1, 1, 1],
                    "metallicFactor": 0,
                    "roughnessFactor": 0.55,
                },
                "alphaMode": "MASK",
                "alphaCutoff": 0.5,
                # Each decal lies on a surface, so its back is never seen; drawing it
                # anyway keeps a decal visible whichever way its quad was wound.
                "doubleSided": True,
            })
        elif name == "readout":
            # The small amber displays: dark glass lit by one cell of the readout atlas.
            m.clear()
            m.update({
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.01, 0.01, 0.01, 1],
                    "metallicFactor": 0,
                    "roughnessFactor": 0.2,
                },
                "emissiveTexture": texture("readouts.png"),
                "emissiveFactor": [1, 1, 1],
                "extensions": {"KHR_materials_emissive_strength": {"emissiveStrength": 3.0}},
                "doubleSided": True,
            })
        elif name == "glass":
            m["doubleSided"] = True
            m["alphaMode"] = "BLEND"
    used = {"KHR_materials_unlit"}
    for m in g["materials"]:
        used |= set(m.get("extensions", {}))
    g["extensionsUsed"] = sorted(used)
    g.pop("extensionsRequired", None)
    g["asset"]["copyright"] = (
        "Model built from code in jeffmhopkins/streamingscenes (cockpit-3d); "
        "textures from ambientCG.com, CC0"
    )
    json.dump(g, open(PATH, "w"), separators=(",", ":"))


main()
