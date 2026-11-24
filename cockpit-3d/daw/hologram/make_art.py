"""Draws the hologram's two pieces of art: the projector's beam and its glow.

    python3 make_art.py [out_dir]

beam.png (512 x 1024): a light cone, narrow at the bottom where the projector is and as
wide as the panel at the top, brightest near its foot, with faint streaks along it; its
last few per cent fade out, so the foot melts into the lens's glow with no hard edge.
glow.png (256 x 256): the projector's lens, a soft glow over the dash: round above its
middle and fading out just below it. The lens's cards stand on the dash, so the dash cuts
them a little under their middle; with nothing left to draw there, the glow meets the dash
softly instead of along a hard line (the hologram's light lights the dash around it).
haze.png (512 x 288): a faint uneven sheet of light, for a card just in front of the panel.
Both are white on transparent, straight alpha: the scene tints them with the hologram's
own colour through a `hologram` effect, so one colour setting changes the whole rig.
"""
import os
import sys

import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))


def beam(w=512, h=1024, foot=0.07):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    v = y / (h - 1)                      # 0 at the top (the panel), 1 at the foot
    half = 0.5 * (1.0 - (1.0 - foot) * v)  # the cone's half width, as a share of w
    u = np.abs(x / (w - 1) - 0.5) / np.maximum(half, 1e-3)
    inside = np.clip(1.0 - u, 0.0, 1.0)
    across = inside ** 0.6 * (0.55 + 0.45 * np.exp(-(u / 0.35) ** 2))
    along = 0.18 + 0.82 * v ** 2.2      # brightest near the foot
    along *= np.clip((1.0 - v) / 0.04, 0.0, 1.0) ** 1.5  # the foot itself fades out
    rng = np.random.default_rng(7)
    streaks = 1.0 + 0.25 * np.interp(x / (w - 1) - 0.5, np.linspace(-0.5, 0.5, 48),
                                     rng.uniform(-1, 1, 48))
    a = np.clip(across * along * streaks * 0.85, 0.0, 1.0)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def glow(s=256):
    y, x = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.hypot(x - (s - 1) / 2, y - (s - 1) / 2) / (s / 2)
    a = np.clip(np.exp(-(r / 0.35) ** 2) + 0.6 * np.exp(-(r / 0.08) ** 2), 0.0, 1.0)
    a *= np.clip((1.0 - r) * 4.0, 0.0, 1.0)
    # Below the middle it fades out within 12% of the radius: smoothstep, so no line.
    below = np.clip((y - (s - 1) / 2) / (0.12 * s / 2), 0.0, 1.0)
    a *= 1.0 - below * below * (3.0 - 2.0 * below)
    rgba = np.zeros((s, s, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def haze(w=512, h=288):
    """A faint sheet of uneven light, for a card just in front of the panel: projected
    light lit up in the air between the panel and the viewer."""
    rng = np.random.default_rng(11)
    n = np.zeros((h, w), np.float32)
    for scale, weight in ((8, 0.5), (16, 0.3), (48, 0.2)):
        small = rng.uniform(0, 1, (h // scale + 2, w // scale + 2)).astype(np.float32)
        img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        n += weight * np.asarray(img, np.float32) / 255
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.clip(np.minimum.reduce([x, w - 1 - x, y, h - 1 - y]) / 60.0, 0, 1)
    a = np.clip((n - 0.25) * 0.35, 0, 0.22) * edge
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


haze().save(os.path.join(OUT, "haze.png"), optimize=True)
beam().save(os.path.join(OUT, "beam.png"), optimize=True)
glow().save(os.path.join(OUT, "glow.png"), optimize=True)
print("wrote beam.png, glow.png and haze.png in", OUT)
