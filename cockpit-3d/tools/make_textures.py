"""Builds the cockpit's texture sets from ambientCG's CC0 2K-JPG downloads.

Usage: python make_textures.py <ambientcg download dir> <out dir>

The download dir holds one folder per ambientCG asset (its 2K-JPG zip unpacked). Each set
becomes three glTF-ready images: <set>-color.jpg (sRGB base colour), <set>-normal.jpg
(OpenGL / glTF normal map) and <set>-orm.jpg (R occlusion, G roughness, B metalness, the
glTF packing, so one image feeds both metallicRoughnessTexture and occlusionTexture).
It also draws the decal atlas and the screens' placeholder cards.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SETS = {
    # set name: (ambientCG id, colour remap or None)
    "paint": ("Metal029", "light"),
    "floor": ("DiamondPlate008A", None),
    "leather": ("Leather034C", None),
    "plastic": ("Plastic012B", None),
    "hexpanel": ("MetalPlates015B", None),
}

FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_MED = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def load(path, mode="L"):
    return Image.open(path).convert(mode)


def build_set(src, out, name, asset, remap):
    base = os.path.join(src, asset, f"{asset}_2K-JPG_")
    color = np.asarray(load(base + "Color.jpg", "RGB")).astype(np.float32)
    if remap == "light":
        # A near-black powder coat, lifted to a warm mid-light grey with its own grain
        # (the grain lifted a little so it still reads at the brighter level).
        lum = color.mean(axis=2, keepdims=True)
        grain = (lum - lum.mean()) * 1.2
        tint = np.array([118.0, 122.0, 128.0])
        color = np.clip(tint + grain, 0, 255)
    Image.fromarray(color.astype(np.uint8)).save(
        os.path.join(out, f"{name}-color.jpg"), quality=92
    )
    load(base + "NormalGL.jpg", "RGB").save(
        os.path.join(out, f"{name}-normal.jpg"), quality=95
    )
    rough = load(base + "Roughness.jpg")
    if remap == "light":
        # Painted, not bare metal: a little rougher, and no metalness (below).
        rough = rough.point(lambda v: min(255, int(v * 0.8 + 70)))
    ao_path = base + "AmbientOcclusion.jpg"
    ao = load(ao_path) if os.path.exists(ao_path) else Image.new("L", rough.size, 255)
    metal_path = base + "Metalness.jpg"
    metal = load(metal_path) if os.path.exists(metal_path) else Image.new("L", rough.size, 0)
    if remap == "light":
        metal = Image.new("L", rough.size, 0)
    Image.merge("RGB", (ao, rough, metal)).save(
        os.path.join(out, f"{name}-orm.jpg"), quality=95
    )


# The decal atlas: 2048 x 2048, eight rows of 256 px. Each entry is a rectangle in pixels;
# build_cockpit.py reads the same table to map its decal planes.
ATLAS = 2048
DECALS = {
    "stripe": (0, 0, 2048, 128),  # hazard stripe, tiles along its length
    "label_nav": (0, 256, 512, 128),
    "label_comms": (512, 256, 512, 128),
    "label_power": (1024, 256, 512, 128),
    "label_sensors": (1536, 256, 512, 128),
    "label_engines": (0, 384, 512, 128),
    "label_shields": (512, 384, 512, 128),
    "label_aux": (1024, 384, 512, 128),
    "label_lifesupport": (1536, 384, 512, 128),
    "warn_eject": (0, 512, 1024, 256),
    "warn_hatch": (1024, 512, 1024, 256),
    "serial": (0, 768, 1024, 128),
    "scale": (1024, 768, 1024, 128),
    "deck_number": (0, 1024, 512, 512),
    "arrow": (512, 1024, 512, 512),
    "keypad": (1024, 1024, 1024, 512),
    "grid_labels": (0, 1536, 2048, 512),
}


def draw_atlas(out):
    im = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bold = lambda s: ImageFont.truetype(FONT, s)
    med = lambda s: ImageFont.truetype(FONT_MED, s)
    white = (232, 232, 226, 255)
    amber = (238, 168, 40, 255)
    black = (20, 20, 20, 255)

    x, y, w, h = DECALS["stripe"]
    for i in range(-2, w // 64 + 2):
        x0 = x + i * 128
        d.polygon([(x0, y), (x0 + 64, y), (x0 + 64 + h, y + h), (x0 + h, y + h)], fill=amber)
        d.polygon(
            [(x0 + 64, y), (x0 + 128, y), (x0 + 128 + h, y + h), (x0 + 64 + h, y + h)],
            fill=black,
        )

    def label(key, text, color=white):
        x, y, w, h = DECALS[key]
        f = bold(64)
        bb = d.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.rectangle([x + 10, y + 12, x + w - 10, y + h - 12], outline=color, width=5)
        d.text((x + (w - tw) / 2 - bb[0], y + (h - th) / 2 - bb[1]), text, font=f, fill=color)

    for key, text in [
        ("label_nav", "NAV"),
        ("label_comms", "COMMS"),
        ("label_power", "POWER"),
        ("label_sensors", "SENSORS"),
        ("label_engines", "ENGINES"),
        ("label_shields", "SHIELDS"),
        ("label_aux", "AUX"),
        ("label_lifesupport", "LIFE SUP"),
    ]:
        label(key, text)

    for key, lines in [
        ("warn_eject", ["EJECT", "PULL HANDLE  -  BOTH HANDS"]),
        ("warn_hatch", ["CAUTION", "HATCH SEAL  -  CHECK PRESSURE"]),
    ]:
        x, y, w, h = DECALS[key]
        d.rectangle([x + 8, y + 8, x + w - 8, y + h - 8], fill=amber)
        d.rectangle([x + 22, y + 22, x + w - 22, y + h - 22], outline=black, width=6)
        f1, f2 = bold(96), med(40)
        for text, f, ty in [(lines[0], f1, y + 40), (lines[1], f2, y + 168)]:
            bb = d.textbbox((0, 0), text, font=f)
            d.text((x + (w - (bb[2] - bb[0])) / 2 - bb[0], ty - bb[1]), text, font=f, fill=black)

    x, y, w, h = DECALS["serial"]
    f = med(52)
    d.text((x + 24, y + 30), "UNIT 07-A   SER 4471-0093   REV C", font=f, fill=white)
    x, y, w, h = DECALS["scale"]
    for i in range(41):
        tx = x + 24 + i * 24
        tall = 80 if i % 10 == 0 else (56 if i % 5 == 0 else 36)
        d.rectangle([tx, y + 16, tx + 4, y + 16 + tall], fill=white)
    x, y, w, h = DECALS["deck_number"]
    f = bold(300)
    bb = d.textbbox((0, 0), "07", font=f)
    d.text((x + (w - (bb[2] - bb[0])) / 2 - bb[0], y + (h - (bb[3] - bb[1])) / 2 - bb[1]), "07",
           font=f, fill=white)
    x, y, w, h = DECALS["arrow"]
    cx, cy = x + w / 2, y + h / 2
    d.polygon([(cx - 60, cy + 180), (cx + 60, cy + 180), (cx + 60, cy - 20), (cx + 150, cy - 20),
               (cx, cy - 190), (cx - 150, cy - 20), (cx - 60, cy - 20)], fill=white)
    x, y, w, h = DECALS["keypad"]
    f = bold(80)
    keys = "123A456B789C*0#D"
    for i, k in enumerate(keys):
        kx, ky = x + 16 + (i % 8) * 126, y + 16 + (i // 8) * 240
        d.rounded_rectangle([kx, ky, kx + 110, ky + 220], 14, outline=white, width=6)
        bb = d.textbbox((0, 0), k, font=f)
        d.text((kx + 55 - (bb[2] - bb[0]) / 2 - bb[0], ky + 110 - (bb[3] - bb[1]) / 2 - bb[1]), k,
               font=f, fill=white)
    x, y, w, h = DECALS["grid_labels"]
    f = med(44)
    words = ["MAIN BUS", "RCS", "FUEL XFER", "GEAR", "CABIN P", "LIGHTS", "COMM 1", "COMM 2",
             "IFF", "MASTER ARM", "BEACON", "PUMP A", "PUMP B", "HEAT", "DAMPER", "TRIM"]
    for i, word in enumerate(words):
        gx, gy = x + (i % 8) * 256, y + (i // 8) * 256
        bb = d.textbbox((0, 0), word, font=f)
        d.text((gx + 128 - (bb[2] - bb[0]) / 2 - bb[0], gy + 30 - bb[1]), word, font=f, fill=white)
        d.line([(gx + 40, gy + 110), (gx + 216, gy + 110)], fill=white, width=4)
        d.text((gx + 40, gy + 130), "ON", font=med(36), fill=white)
        d.text((gx + 160, gy + 130), "OFF", font=med(36), fill=white)
    px = np.asarray(im).copy()
    clear = px[..., 3] == 0
    px[clear, :3] = 200
    Image.fromarray(px).save(os.path.join(out, "decals.png"), optimize=True)


SCREENS = ["screen_center", "screen_left", "screen_right", "screen_side_left",
           "screen_side_right", "screen_overhead"]


def draw_screens(out):
    """A test card per screen, 960 x 540 (16:9), naming its material, so the screens are
    easy to tell apart until a live source replaces them."""
    for name in SCREENS:
        w, h = 960, 540
        im = Image.new("RGB", (w, h), (8, 14, 22))
        d = ImageDraw.Draw(im)
        for gx in range(0, w + 1, 60):
            d.line([(gx, 0), (gx, h)], fill=(20, 48, 64), width=1)
        for gy in range(0, h + 1, 60):
            d.line([(0, gy), (w, gy)], fill=(20, 48, 64), width=1)
        d.rectangle([2, 2, w - 3, h - 3], outline=(60, 200, 230), width=4)
        bars = [(230, 230, 230), (230, 230, 40), (40, 230, 230), (40, 230, 40), (230, 40, 230),
                (230, 40, 40), (40, 40, 230)]
        bw = (w - 160) // len(bars)
        for i, c in enumerate(bars):
            d.rectangle([80 + i * bw, 330, 80 + (i + 1) * bw, 420], fill=c)
        f = ImageFont.truetype(FONT, 64)
        bb = d.textbbox((0, 0), name, font=f)
        d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], 150 - bb[1]), name, font=f, fill=(220, 245, 255))
        f2 = ImageFont.truetype(FONT_MED, 30)
        t = "material  ·  16:9  ·  top-left is up-left"
        bb = d.textbbox((0, 0), t, font=f2)
        d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], 250 - bb[1]), t, font=f2, fill=(120, 200, 220))
        d.polygon([(12, 12), (72, 12), (12, 72)], fill=(255, 80, 60))
        im.save(os.path.join(out, f"{name}.jpg"), quality=90)


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name, (asset, remap) in SETS.items():
        build_set(src, out, name, asset, remap)
    draw_atlas(out)
    draw_screens(out)


if __name__ == "__main__":
    main()
