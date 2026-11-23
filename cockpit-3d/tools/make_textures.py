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
    "paint": ("Metal029", "grime"),
    "floor": ("DiamondPlate008A", None),
    "leather": ("Leather034C", None),
    "plastic": ("Plastic012B", None),
    "hexpanel": ("MetalPlates015B", None),
}

PAINT_TINT = [50.0, 57.0, 68.0]  # dark blue-grey gunmetal paint

FONT = "/usr/share/fonts/opentype/inter/Inter-Bold.otf"
FONT_MED = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"


def tile_noise(n, cycles, seed):
    """Tileable smooth noise in -1..1: white noise low-passed in frequency space, so it
    wraps at the edges. `cycles` is roughly how many blobs fit across."""
    rng = np.random.default_rng(seed)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    k = np.fft.fftfreq(n) * n
    kk = np.sqrt(k[:, None] ** 2 + k[None, :] ** 2)
    out = np.real(np.fft.ifft2(f * np.exp(-(kk / cycles) ** 2)))
    return out / (np.abs(out).max() + 1e-9)


def grime_mask(n, seed):
    """0..1 dirt: large stains broken up by finer noise, mostly clean."""
    v = (tile_noise(n, 3, seed) * 0.55 + tile_noise(n, 12, seed + 1) * 0.3
         + tile_noise(n, 60, seed + 2) * 0.15)
    return np.clip((v - 0.05) / 0.45, 0, 1) ** 1.5


def scratch_mask(n, seed):
    """0..1 fine scratches, drawn wrapped so the texture still tiles."""
    rng = np.random.default_rng(seed)
    im = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(im)
    for _ in range(900):
        x, y = rng.uniform(0, n, 2)
        ang = rng.normal(0.3, 0.5) if rng.random() < 0.7 else rng.uniform(0, np.pi)
        length = rng.exponential(40) + 6
        x1, y1 = x + np.cos(ang) * length, y + np.sin(ang) * length
        level = int(rng.uniform(60, 200))
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                d.line([(x + ox, y + oy), (x1 + ox, y1 + oy)], fill=level, width=1)
    return np.asarray(im).astype(np.float32) / 255.0


def load(path, mode="L"):
    return Image.open(path).convert(mode)


def build_set(src, out, name, asset, remap):
    base = os.path.join(src, asset, f"{asset}_2K-JPG_")
    color = np.asarray(load(base + "Color.jpg", "RGB")).astype(np.float32)
    grime = scratches = None
    if remap == "grime":
        # Dark blue-grey paint over the powder coat's grain, with tiling grime and scratches.
        n = color.shape[0]
        lum = color.mean(axis=2, keepdims=True)
        grain = (lum - lum.mean()) * 1.0
        tint = np.array(PAINT_TINT)
        grime = grime_mask(n, seed=7)[..., None]
        scratches = scratch_mask(n, seed=11)[..., None]
        mottling = tile_noise(n, 6, seed=3)[..., None] * 10.0
        dirt = np.array([34.0, 31.0, 27.0])
        color = tint + grain + mottling
        color = color * (1 - grime * 0.6) + dirt * grime * 0.6
        color = color * (1 - scratches) + np.array([128.0, 132.0, 138.0]) * scratches
        color = np.clip(color, 0, 255)
    Image.fromarray(color.astype(np.uint8)).save(
        os.path.join(out, f"{name}-color.jpg"), quality=92
    )
    load(base + "NormalGL.jpg", "RGB").save(
        os.path.join(out, f"{name}-normal.jpg"), quality=95
    )
    rough = load(base + "Roughness.jpg")
    if remap == "grime":
        # Paint: rougher where dirty, glossy bare metal in the scratches.
        r = np.asarray(rough).astype(np.float32) * 0.6 + 90
        r = r + grime[..., 0] * 70
        r = r * (1 - scratches[..., 0]) + 70 * scratches[..., 0]
        rough = Image.fromarray(np.clip(r, 0, 255).astype(np.uint8))
    ao_path = base + "AmbientOcclusion.jpg"
    ao = load(ao_path) if os.path.exists(ao_path) else Image.new("L", rough.size, 255)
    metal_path = base + "Metalness.jpg"
    metal = load(metal_path) if os.path.exists(metal_path) else Image.new("L", rough.size, 0)
    if remap == "grime":
        metal = Image.fromarray((np.clip(scratches[..., 0], 0, 1) * 255).astype(np.uint8))
        ao = Image.fromarray(
            (np.asarray(ao).astype(np.float32) * (1 - grime[..., 0] * 0.3)).astype(np.uint8))
    Image.merge("RGB", (ao, rough, metal)).save(
        os.path.join(out, f"{name}-orm.jpg"), quality=95
    )


def blur_wrap(a, sigma):
    """Gaussian blur that wraps at the edges, so the result still tiles."""
    n = a.shape[0]
    k = np.fft.fftfreq(n)
    g = np.exp(-2 * (np.pi * sigma) ** 2 * (k[:, None] ** 2 + k[None, :] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def build_panel_set(src, out, n=2048):
    """The `panel` set, for the big surfaces: painted metal panelling drawn here over the
    paint set's grain. Seams between panels, rivets along them, each panel a slightly
    different shade and height, paint chipped to bare metal along the seams and on the
    rivet heads, and grime settled in the grooves. It tiles."""
    rng = np.random.default_rng(42)
    seam = Image.new("L", (n, n), 0)
    rivet = Image.new("L", (n, n), 0)
    shade = np.zeros((n, n), np.float32)
    level = np.zeros((n, n), np.float32)
    ds, dr = ImageDraw.Draw(seam), ImageDraw.Draw(rivet)
    rects = [(0, 0, n, n)]
    for _ in range(4):
        nxt = []
        for x0, y0, x1, y1 in rects:
            w, h = x1 - x0, y1 - y0
            if max(w, h) < 380 or rng.random() < 0.12:
                nxt.append((x0, y0, x1, y1))
            elif w >= h:
                c = int(x0 + w * rng.uniform(0.35, 0.65))
                nxt += [(x0, y0, c, y1), (c, y0, x1, y1)]
            else:
                c = int(y0 + h * rng.uniform(0.35, 0.65))
                nxt += [(x0, y0, x1, c), (x0, c, x1, y1)]
        rects = nxt
    for x0, y0, x1, y1 in rects:
        shade[y0:y1, x0:x1] = rng.uniform(-7, 7)
        level[y0:y1, x0:x1] = rng.choice([0.0, 0.0, 0.35, -0.3])
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                ds.rectangle([x0 + ox, y0 + oy, x1 + ox, y1 + oy], outline=255, width=5)
        inset, pitch = 26, 72
        pts = []
        for x in np.arange(x0 + inset, x1 - inset + 1, max(pitch, 1)):
            pts += [(x, y0 + inset), (x, y1 - inset)]
        for y in np.arange(y0 + inset + pitch, y1 - inset - pitch + 1, pitch):
            pts += [(x0 + inset, y), (x1 - inset, y)]
        for x, y in pts:
            dr.ellipse([x - 6, y - 6, x + 6, y + 6], fill=255)
    S = np.asarray(seam).astype(np.float32) / 255
    R = blur_wrap(np.asarray(rivet).astype(np.float32) / 255, 1.5)
    S1, S8, S30 = blur_wrap(S, 1.2), blur_wrap(S, 7), blur_wrap(S, 30)
    # Height: grooves at the seams, domes at the rivets, panels at slightly different levels.
    height = -S1 * 1.4 + blur_wrap(np.asarray(rivet).astype(np.float32) / 255, 3) * 2.2 \
        + blur_wrap(level, 3) * 1.5
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 2.2
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 2.2
    base_n = np.asarray(load(os.path.join(src, "Metal029", "Metal029_2K-JPG_NormalGL.jpg"),
                             "RGB").resize((n, n))).astype(np.float32) / 127.5 - 1
    nx, ny = -gx + base_n[..., 0] * 0.5, gy + base_n[..., 1] * 0.5  # image y is down
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / ln, ny / ln, nz / ln], -1)
    Image.fromarray(((normal * 0.5 + 0.5) * 255).astype(np.uint8)).save(
        os.path.join(out, "panel-normal.jpg"), quality=95)
    # Chipped paint: a band beside each seam and the rivet heads, broken up by noise.
    band = np.clip(S8 * 6, 0, 1) * (1 - np.clip(S1 * 3, 0, 1))
    chips = np.clip((band * 0.9 + tile_noise(n, 90, 5) * 0.55 + tile_noise(n, 300, 6) * 0.35 - 0.95) * 6, 0, 1)
    chips = np.clip(chips + np.clip(R * 1.6 - 0.5, 0, 1) * np.clip(tile_noise(n, 40, 8) * 2 + 0.6, 0, 1), 0, 1)
    scratches = scratch_mask(n, seed=21) * 0.7
    grime = np.clip(grime_mask(n, seed=17) * 0.8 + np.clip(S30 * 5, 0, 1) * 0.55, 0, 1)
    grain_src = np.asarray(load(os.path.join(src, "Metal029", "Metal029_2K-JPG_Color.jpg"),
                                "RGB").resize((n, n))).astype(np.float32).mean(axis=2)
    grain = grain_src - grain_src.mean()
    lum = (shade + grain + tile_noise(n, 5, 13) * 8)[..., None]
    color = np.array(PAINT_TINT) + lum
    dirt, bare = np.array([26.0, 23.0, 20.0]), np.array([118.0, 121.0, 126.0])
    g3 = grime[..., None]
    color = color * (1 - g3 * 0.65) + dirt * g3 * 0.65
    color = color * (1 - np.clip(S1 * 1.5, 0, 1)[..., None] * 0.8)
    m = np.clip(chips + scratches, 0, 1)[..., None]
    color = color * (1 - m) + bare * m
    Image.fromarray(np.clip(color, 0, 255).astype(np.uint8)).save(
        os.path.join(out, "panel-color.jpg"), quality=92)
    # Matte paint, rougher where dirty; bare metal is glossy and metallic.
    rough = 150 + grime * 70 + tile_noise(n, 20, 31) * 14
    rough = rough * (1 - m[..., 0]) + 62 * m[..., 0]
    ao = 255 * (1 - np.clip(S8 * 2.2, 0, 1) * 0.55) * (1 - grime * 0.2)
    metal = m[..., 0] * 255
    Image.fromarray(np.clip(np.stack([ao, rough, metal], -1), 0, 255).astype(np.uint8)).save(
        os.path.join(out, "panel-orm.jpg"), quality=95)


def build_grunge_set(out, n=2048):
    """Replaces the `panel` set with grungy metal: no seams or rivets, just worn gunmetal
    built over the paint set already in `out` (its grain, grime and scratches). Heavier
    weathering on top: broad stains, dirt streaked downward, patches worn through to bare
    metal with dark edges, pitting and fine dents. It tiles.

        python make_textures.py --grunge <textures dir>
    """
    paint = np.asarray(load(os.path.join(out, "paint-color.jpg"), "RGB").resize((n, n))
                       ).astype(np.float32)
    p_orm = np.asarray(load(os.path.join(out, "paint-orm.jpg"), "RGB").resize((n, n))
                       ).astype(np.float32)
    p_nrm = np.asarray(load(os.path.join(out, "paint-normal.jpg"), "RGB").resize((n, n))
                       ).astype(np.float32) / 127.5 - 1
    # Broad stains, and dirt run down the surface: noise stretched tall, so it streaks.
    stains = np.clip(tile_noise(n, 4, 51) * 0.7 + tile_noise(n, 16, 52) * 0.3, -1, 1)
    rng = np.random.default_rng(53)
    f = np.fft.fft2(rng.standard_normal((n, n)))
    k = np.fft.fftfreq(n) * n
    streak = np.real(np.fft.ifft2(f * np.exp(-(k[None, :] / 40) ** 2 - (k[:, None] / 3) ** 2)))
    streak = streak / (np.abs(streak).max() + 1e-9)
    dirt = np.clip(stains * 0.6 + streak * 0.7 + grime_mask(n, 54) * 0.6 - 0.15, 0, 1)
    # Wear: patches through the paint to bare metal, ragged at their edges.
    wear_v = tile_noise(n, 7, 55) * 0.6 + tile_noise(n, 70, 56) * 0.3 + tile_noise(n, 260, 57) * 0.25
    wear = np.clip((wear_v - 0.42) * 7, 0, 1)
    rim = np.clip(1 - np.abs(wear_v - 0.36) * 22, 0, 1) * (1 - wear)
    # Pitting: small dark pocks, and soft dents.
    pits = np.clip((tile_noise(n, 500, 58) - 0.55) * 6, 0, 1) * np.clip(dirt * 1.5 + 0.2, 0, 1)
    dents = tile_noise(n, 25, 59)
    scratches = scratch_mask(n, seed=60) * 0.8
    bare = np.array([112.0, 115.0, 120.0]) + (paint.mean(2, keepdims=True) - paint.mean()) * 0.8
    color = paint * (1 - dirt[..., None] * 0.55) + np.array([24.0, 22.0, 19.0]) * dirt[..., None] * 0.55
    color = color * (1 - rim[..., None] * 0.45)
    m = np.clip(wear * 0.85 + scratches * (1 - dirt * 0.6), 0, 1)
    color = color * (1 - m[..., None]) + bare * m[..., None]
    color = color * (1 - pits[..., None] * 0.6)
    Image.fromarray(np.clip(color, 0, 255).astype(np.uint8)).save(
        os.path.join(out, "panel-color.jpg"), quality=92)
    height = dents * 0.4 - pits * 1.2 - rim * 0.4 + wear * -0.25
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 2.0
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 2.0
    nx, ny = -gx * 3 + p_nrm[..., 0] * 0.6, gy * 3 + p_nrm[..., 1] * 0.6
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack([nx / ln, ny / ln, nz / ln], -1)
    Image.fromarray(((normal * 0.5 + 0.5) * 255).astype(np.uint8)).save(
        os.path.join(out, "panel-normal.jpg"), quality=95)
    rough = p_orm[..., 1] * 0.5 + 95 + dirt * 70 - m * 60 + pits * 40
    ao = p_orm[..., 0] * (1 - dirt * 0.25) * (1 - pits * 0.4)
    metal = np.maximum(p_orm[..., 2], m * 255)
    Image.fromarray(np.clip(np.stack([ao, rough, metal], -1), 0, 255).astype(np.uint8)).save(
        os.path.join(out, "panel-orm.jpg"), quality=95)


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


# Every screen shares one material, `screens`, and one 1920 x 1080 image: a 3 x 3 grid of
# 640 x 360 cells, (column, row) from the top left. The desk instrument is 8:3 and takes
# the left 960 x 360 of the bottom row.
SCREEN_CELLS = {
    "screen_left": (0, 0), "screen_center": (1, 0), "screen_right": (2, 0),
    "screen_overhead_left": (0, 1), "screen_overhead_right": (1, 1), "screen_side_left": (2, 1),
    "screen_desk": (0, 2), "screen_side_right": (2, 2),
}
SCREENS = list(SCREEN_CELLS)

# Readouts: an emissive atlas of small amber displays, 8 x 16 cells of 256 x 128 px.
# build_cockpit.py picks cells for the little display quads on the panels.
READOUT_COLS, READOUT_ROWS = 8, 16


def seg_digit(d, x, y, w, h, ch, fill):
    """A seven-segment character at (x, y), w x h."""
    segs = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
            "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": ""}[ch]
    t = max(2, w // 6)
    pts = {"a": (x + t, y, x + w - t, y + t), "g": (x + t, y + h // 2 - t // 2, x + w - t, y + h // 2 + t // 2),
           "d": (x + t, y + h - t, x + w - t, y + h), "f": (x, y + t, x + t, y + h // 2),
           "b": (x + w - t, y + t, x + w, y + h // 2), "e": (x, y + h // 2, x + t, y + h - t),
           "c": (x + w - t, y + h // 2, x + w, y + h - t)}
    for sname in segs:
        d.rectangle(pts[sname], fill=fill)


def draw_readouts(out):
    rng = np.random.default_rng(5)
    W, H = 256, 128
    im = Image.new("RGB", (W * READOUT_COLS, H * READOUT_ROWS), (0, 0, 0))
    d = ImageDraw.Draw(im)
    amber = [(255, 150, 30), (255, 120, 10), (255, 180, 70), (230, 90, 10)]
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 16)
    for r in range(READOUT_ROWS):
        for c in range(READOUT_COLS):
            x, y = c * W, r * H
            col = amber[rng.integers(len(amber))]
            dim = tuple(int(v * 0.25) for v in col)
            d.rectangle([x + 4, y + 4, x + W - 5, y + H - 5], fill=(10, 6, 3))
            kind = (r * READOUT_COLS + c) % 6
            if kind == 0:  # seven-segment numbers
                text = "".join(str(rng.integers(10)) for _ in range(rng.integers(3, 6)))
                cw = (W - 30) // 5
                for i, ch in enumerate(text.rjust(5)):
                    seg_digit(d, x + 15 + i * cw + 4, y + 22, cw - 12, H - 44, "8", dim)
                    seg_digit(d, x + 15 + i * cw + 4, y + 22, cw - 12, H - 44, ch, col)
            elif kind == 1:  # bar graph
                n = 12
                for i in range(n):
                    hgt = int(rng.uniform(0.15, 1.0) * (H - 40))
                    bx = x + 14 + i * (W - 28) // n
                    d.rectangle([bx, y + H - 18 - (H - 40), bx + 10, y + H - 18], fill=dim)
                    d.rectangle([bx, y + H - 18 - hgt, bx + 10, y + H - 18], fill=col)
            elif kind == 2:  # text lines
                for i in range(5):
                    line = "".join(rng.choice(list("ABCDEFGHJKLMNPRSTUVXYZ0123456789 .:-"), 22))
                    d.text((x + 12, y + 10 + i * 21), line, font=f, fill=col if i % 2 == 0 else dim)
            elif kind == 3:  # segmented level strips
                for row in range(3):
                    lit = rng.integers(3, 16)
                    for i in range(16):
                        bx = x + 12 + i * 14
                        by = y + 18 + row * 32
                        d.rectangle([bx, by, bx + 10, by + 20], fill=col if i < lit else dim)
            elif kind == 4:  # waveform
                pts = []
                ph, fq = rng.uniform(0, 6), rng.uniform(2, 6)
                for i in range(W - 24):
                    t = i / (W - 24)
                    v = np.sin(t * fq * 6.28 + ph) * 0.6 + rng.normal(0, 0.08)
                    pts.append((x + 12 + i, y + H / 2 - v * (H / 2 - 16)))
                d.line([(x + 12, y + H // 2), (x + W - 12, y + H // 2)], fill=dim, width=1)
                d.line(pts, fill=col, width=3)
            else:  # dot matrix of status lights
                for gy in range(4):
                    for gx in range(10):
                        bx, by = x + 16 + gx * 23, y + 16 + gy * 25
                        on = rng.random() > 0.45
                        d.ellipse([bx, by, bx + 14, by + 14], fill=col if on else dim)
    im.save(os.path.join(out, "readouts.png"), optimize=True)


def draw_screens(out):
    """A test card per screen, 960 x 540 (16:9), naming its material, so the screens are
    easy to tell apart until a live source replaces them."""
    # The desk instrument, switched off: a dark 24 x 8 grid of pads, 1536 x 576 (8:3). A
    # live source on screen_desk replaces it.
    w, h = 1536, 576
    im = Image.new("RGB", (w, h), (6, 6, 7))
    d = ImageDraw.Draw(im)
    for r in range(8):
        for c in range(24):
            x, y = 12 + c * 63, 12 + r * 69
            shade = 40 + ((r * 5 + c * 7) % 4) * 3
            d.rounded_rectangle([x, y, x + 55, y + 61], 6, fill=(shade, shade, shade + 2),
                                outline=(70, 70, 76), width=2)
    atlas = Image.new("RGB", (1920, 1080), (0, 0, 0))
    c, r = SCREEN_CELLS["screen_desk"]
    atlas.paste(im.resize((960, 360), Image.LANCZOS), (c * 640, r * 360))
    for name in SCREENS:
        if name == "screen_desk":
            continue
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
        c, r = SCREEN_CELLS[name]
        atlas.paste(im.resize((640, 360), Image.LANCZOS), (c * 640, r * 360))
    # The console's live panels (live_panels.py) show the strip right of the desk's cell:
    # until a live source fills it, it holds what those panels showed before.
    from live_panels import draw_placeholders
    draw_placeholders(atlas, Image.open(os.path.join(out, "readouts.png")).convert("RGB"))
    atlas.save(os.path.join(out, "screens.jpg"), quality=92)


def main():
    if sys.argv[1] == "--grunge":
        build_grunge_set(sys.argv[2])
        return
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name, (asset, remap) in SETS.items():
        build_set(src, out, name, asset, remap)
    build_panel_set(src, out)
    draw_atlas(out)
    draw_readouts(out)
    draw_screens(out)  # after the readouts: the live panels' placeholders copy them


if __name__ == "__main__":
    main()
