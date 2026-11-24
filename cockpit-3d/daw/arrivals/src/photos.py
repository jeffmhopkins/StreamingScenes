"""Nebula photographs (arrivals/photos/*.jpg, portrait) to arrival pictures: turned to
landscape, their edges dissolved into the sky, and their dark sky made transparent.

Three things make a photo read as gas in the sky rather than a picture pasted on it:

- Its frame goes. Alpha falls off over a wide band in from the edges, and the band's
  inner edge is pushed in and out by fractal noise and by the picture itself: bright gas
  reaches further out, dark gaps fade sooner. So the outline is a cloud's, never a
  rectangle's or an ellipse's.
- Its sky goes. Light is opacity: the black between the clouds is transparent and the
  real stars behind show through it. A little of the dark stays as dust (`DUST`), so the
  thick lanes still dim the stars behind them.
- Its colour is unpremultiplied, so over black it looks just as the photo did.

`python3 photos.py [name ...]` writes arrivals/<name>.png (1152 x 768, RGBA) for each photo,
or the ones named. `--preview DIR` also writes each one over a starfield, and a contact
sheet, to DIR.
"""
import os
import sys

import numpy as np
from PIL import Image

from common import Perlin3, blur, fbm, grid, smooth

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
SRC = os.path.join(ART, "photos")

# Per photo: which way to turn it (degrees counter-clockwise; 90 or -90 turns portrait to
# landscape), the noise seed for its outline, and how far in the fade reaches (0 to 1 of
# the half short side).
PHOTOS = {
    "cloud_hood": dict(turn=-90, seed=31),
    "red_cliffs": dict(turn=90, seed=32),
    "blue_veils": dict(turn=-90, seed=33),
    "violet_rays": dict(turn=90, seed=34),
    "crimson_dust": dict(turn=-90, seed=35),
    "rainbow_pillar": dict(turn=-90, seed=36),
    "ember_dust": dict(turn=90, seed=37),
    "silver_veil": dict(turn=-90, seed=38),
    "bubble_cluster": dict(turn=90, seed=39),
}
FLOOR = 6  # the photo's sky: its darkest this-percent of light is taken off as a black level
GAIN = 1.6  # light to opacity, over that black level
DUST = 0.3  # how much the darkest parts inside still dim the stars behind
FADE = 0.95  # the fade band's width, as a share of the half short side


def outline(w, h, light, seed, fade=FADE):
    """The organic fade: 1 well inside, 0 at and well in from the frame."""
    x, y = grid(w, h)  # long side -1..1
    ry = h / w
    # Distance in from the nearest edge, as a share of the half short side, rounded at
    # the corners so they melt first.
    dx = (1 - np.abs(x)) / ry
    dy = (ry - np.abs(y)) / ry
    k = 4.0
    d = np.maximum(-np.log(np.exp(-k * dx) + np.exp(-k * dy)) / k, 0)
    base = smooth(0.0, fade, d)
    # Cloud noise, spread to 0..1 by rank, mixed with the picture's own light so bright
    # gas holds on further out and dark gaps let go sooner.
    n = Perlin3(seed)
    c = fbm(n, x * 2.2, y * 2.2, 0.3, 6)
    lum = blur(light, w / 50)
    c = 0.65 * _rank(c) + 0.35 * _rank(lum)
    # The nearer the frame, the more of the cloud is eaten away, softly.
    t = 1 - base
    m = smooth(t - 0.55, t + 0.3, c) * base ** 0.6
    # Blurred so no lobe has a hard rim, then eased so the faint outer haze thins out
    # to nothing gradually instead of ending in a visible line.
    return np.clip(blur(m, w / 40), 0, 1) ** 1.5


def _rank(a):
    r = np.empty(a.size)
    r[np.argsort(a, axis=None)] = np.linspace(0, 1, a.size)
    return r.reshape(a.shape)


def process(name, turn, seed):
    im = Image.open(os.path.join(SRC, f"{name}.jpg")).convert("RGB")
    im = im.rotate(turn, expand=True)
    rgb = np.asarray(im, np.float64) / 255.0
    rgb = rgb ** 2.2  # to linear light
    h, w = rgb.shape[:2]
    edge = outline(w, h, rgb.max(axis=-1), seed)
    # The photo's dark sky is a grey veil, not black: take it off as a black level, more
    # of it toward the edge, so the faint haze there thins to nothing instead of ending
    # in a visible line.
    floor = np.percentile(rgb.max(axis=-1), FLOOR)
    lift = floor * (1.0 + 1.5 * (1 - edge))[..., None]
    rgb = np.clip(rgb - lift, 0, None) / (1 - floor)
    light = rgb.max(axis=-1)
    a_light = np.clip(light * GAIN, 0, 1) ** 0.6
    # Dust: where the photo is dark but sits in gas (bright around it).
    around = blur(light, w / 60)
    dust = DUST * smooth(0.04, 0.3, around) * (1 - a_light) * edge
    alpha = (1 - (1 - a_light) * (1 - dust)) * edge
    shown = rgb * edge[..., None]  # what shows over black: the photo, faded out
    col = np.where(alpha[..., None] > 1e-4, shown / np.maximum(alpha, 1e-4)[..., None], 0)
    col = np.clip(col, 0, 1) ** (1 / 2.2)
    a8 = np.clip(alpha, 0, 1)
    out = np.dstack([col, a8])
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def starfield(w, h, seed=7):
    r = np.random.default_rng(seed)
    img = np.zeros((h, w, 3)) + np.array([0.004, 0.005, 0.012])
    n = 1400
    xs, ys = r.integers(0, w, n), r.integers(0, h, n)
    m = (r.pareto(2.0, n) + 0.15)
    m = np.clip(m / 3, 0, 1)
    for x, y, a in zip(xs, ys, m):
        img[y, x] += a
    img = img + blur(img, 1.2) * 2.5
    return np.clip(img, 0, 1)


def over(bg, rgba):
    a = np.asarray(rgba, np.float64)[..., 3:] / 255.0
    c = np.asarray(rgba, np.float64)[..., :3] / 255.0
    lin = c ** 2.2 * a + bg ** 2.2 * (1 - a)
    return Image.fromarray((np.clip(lin, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))


def main(argv):
    preview = None
    if "--preview" in argv:
        i = argv.index("--preview")
        preview = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    names = argv or list(PHOTOS)
    shots = []
    for name in names:
        pic = process(name, **PHOTOS[name])
        pic.save(os.path.join(ART, f"{name}.png"), optimize=True)
        print(name, pic.size)
        if preview:
            os.makedirs(preview, exist_ok=True)
            # The picture over the sky, with sky all round, as it would sit in the window.
            W, H = int(pic.width * 1.4), int(pic.height * 1.4)
            bg = starfield(W, H, seed=hash(name) % 1000)
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            canvas.paste(pic, ((W - pic.width) // 2, (H - pic.height) // 2))
            shot = over(bg, canvas)
            shot.save(os.path.join(preview, f"{name}.jpg"), quality=90)
            shots.append((name, shot))
    if preview and shots:
        tw = 640
        th = round(tw * shots[0][1].height / shots[0][1].width)
        cols = 3
        rows = (len(shots) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (12, 12, 16))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        for k, (name, shot) in enumerate(shots):
            x, y = (k % cols) * tw, (k // cols) * (th + 22)
            sheet.paste(shot.resize((tw, th), Image.LANCZOS), (x, y + 22))
            d.text((x + 6, y + 5), name, fill=(220, 220, 230))
        sheet.save(os.path.join(preview, "contact-sheet.jpg"), quality=88)


if __name__ == "__main__":
    main(sys.argv[1:])
