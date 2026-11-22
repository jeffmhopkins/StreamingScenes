# Credits and licences

## The model

`cockpit.gltf` and `cockpit.bin` were built for this repository from code
([`../tools/build_cockpit.py`](../tools/build_cockpit.py)). No third-party geometry is in them.

## Textures

The tiling texture sets are made from these [ambientCG](https://ambientcg.com) materials, which are
released under **CC0 1.0** (public domain, no attribution required). They are credited here anyway.
[`../tools/make_textures.py`](../tools/make_textures.py) repacks them for glTF: an occlusion, roughness and
metalness image per set, and the paint set is recoloured from near black to a dark blue-grey, with generated grime and scratches.

| Set | ambientCG asset | Licence |
|---|---|---|
| `paint` (also `paint_dark`) | [Metal029](https://ambientcg.com/view?id=Metal029) | CC0 1.0 |
| `floor` | [DiamondPlate008A](https://ambientcg.com/view?id=DiamondPlate008A) | CC0 1.0 |
| `leather` | [Leather034C](https://ambientcg.com/view?id=Leather034C) | CC0 1.0 |
| `plastic` | [Plastic012B](https://ambientcg.com/view?id=Plastic012B) | CC0 1.0 |
| `hexpanel` | [MetalPlates015B](https://ambientcg.com/view?id=MetalPlates015B) | CC0 1.0 |
| `panel` | grungy metal drawn by `make_textures.py --grunge` over the `paint` set (grain of [Metal029](https://ambientcg.com/view?id=Metal029)) | CC0 1.0 |

ambientCG's licence: <https://docs.ambientcg.com/license/>.

`decals.png`, `readouts.png` and the `screens.jpg` placeholder atlas are drawn by `make_textures.py`. The grime and scratches on the `paint` set are generated there too. Their text is
set in [Inter](https://github.com/rsms/inter) (SIL Open Font License 1.1). Only rendered images of the
glyphs are in the textures, not the font.
