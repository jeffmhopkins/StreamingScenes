"""Shared pieces for the arrival pictures: gradient noise, colour, blur, tonemapping and
saving with supersampling."""
import os

import numpy as np
from PIL import Image


class Perlin3:
    """Gradient (Perlin) noise in 3D, about -1 to 1, on a seeded, hashed lattice. Works
    on arrays of any shape."""

    def __init__(self, seed):
        r = np.random.default_rng(seed)
        self.p = np.concatenate([r.permutation(256)] * 2).astype(np.int64)
        g = r.normal(size=(256, 3))
        self.g = (g / np.linalg.norm(g, axis=1, keepdims=True)).astype(np.float64)

    def __call__(self, x, y, z):
        x, y, z = np.asarray(x, np.float64), np.asarray(y, np.float64), np.asarray(z, np.float64)
        x, y, z = np.broadcast_arrays(x, y, z)
        xi, yi, zi = (np.floor(a).astype(np.int64) & 255 for a in (x, y, z))
        xf, yf, zf = x - np.floor(x), y - np.floor(y), z - np.floor(z)
        u, v, w = (t * t * t * (t * (t * 6 - 15) + 10) for t in (xf, yf, zf))
        p, g = self.p, self.g
        out = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    hsh = p[p[p[xi + dx] + yi + dy] + zi + dz]
                    gr = g[hsh]
                    dot = gr[..., 0] * (xf - dx) + gr[..., 1] * (yf - dy) + gr[..., 2] * (zf - dz)
                    wt = (u if dx else 1 - u) * (v if dy else 1 - v) * (w if dz else 1 - w)
                    out = out + wt * dot
        return out * 1.6


def fbm(noise, x, y, z, octaves=6, lac=2.03, gain=0.5):
    """Fractal noise, about 0 to 1."""
    total, amp, norm = 0.0, 1.0, 0.0
    for _ in range(octaves):
        total = total + amp * noise(x, y, z)
        norm += amp
        x, y, z = x * lac + 17.31, y * lac + 5.13, z * lac + 9.71
        amp *= gain
    return 0.5 + 0.5 * total / norm


def ridged(noise, x, y, z, octaves=6, lac=2.07, gain=0.55):
    """Ridged fractal noise, 0 to 1: thin bright ridges, for filaments and cracks."""
    total, amp, norm = 0.0, 1.0, 0.0
    for _ in range(octaves):
        total = total + amp * (1 - np.abs(noise(x, y, z))) ** 3
        norm += amp
        x, y, z = x * lac + 3.37, y * lac + 1.79, z * lac + 7.93
        amp *= gain
    return total / norm


def warp(noise, x, y, z, k=1.0, octaves=4):
    """Domain warping: offsets for (x, y, z) from noise, for turbulent, swirling shapes."""
    return (x + k * (fbm(noise, x + 1.7, y + 9.2, z, octaves) - 0.5) * 2,
            y + k * (fbm(noise, x + 8.3, y + 2.8, z + 3.1, octaves) - 0.5) * 2,
            z + k * (fbm(noise, x + 4.1, y + 6.6, z + 7.7, octaves) - 0.5) * 2)


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def ramp(t, stops):
    """Colour from `stops` [(at, (r, g, b)), ...] at t (0 to 1), smoothly."""
    t = np.clip(np.asarray(t, np.float64), 0, 1)
    out = np.zeros(t.shape + (3,))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        m = (t >= a) & (t <= b)
        k = smooth(0, 1, (t[m] - a) / max(b - a, 1e-9))[..., None]
        out[m] = np.array(ca) * (1 - k) + np.array(cb) * k
    return out


def mix(a, b, t):
    t = np.asarray(t)[..., None] if np.ndim(t) else t
    return a * (1 - t) + b * t


def blackbody(temp):
    """The colour of a black body at `temp` kelvin, its largest channel 1 (Tanner
    Helland's fit, smoothed)."""
    t = np.clip(np.asarray(temp, np.float64), 1000, 40000) / 100
    r = np.where(t <= 66, 255, 329.698727446 * np.power(np.maximum(t - 60, 1e-6), -0.1332047592))
    g = np.where(t <= 66, 99.4708025861 * np.log(t) - 161.1195681661,
                 288.1221695283 * np.power(np.maximum(t - 60, 1e-6), -0.0755148492))
    b = np.where(t >= 66, 255, np.where(t <= 19, 0, 138.5177312231 * np.log(np.maximum(t - 10, 1e-6)) - 305.0447927307))
    c = np.clip(np.stack([r, g, b], -1) / 255, 0, 1)
    return c / np.maximum(c.max(axis=-1, keepdims=True), 1e-6)


def tonemap(x):
    """HDR to 0..1, keeping hue: a smooth shoulder on the brightest channel."""
    m = np.max(x, axis=-1, keepdims=True)
    mm = 1 - np.exp(-m)
    return np.clip(x * (mm / np.maximum(m, 1e-9)), 0, 1)


def _blur1(a, sigma, axis):
    n = a.shape[axis]
    pad = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-pad, pad + 1) / sigma) ** 2)
    k /= k.sum()
    size = n + 2 * pad
    fk = np.fft.rfft(k, size)
    shape = [1] * a.ndim
    shape[axis] = -1
    pw = [(0, 0)] * a.ndim
    pw[axis] = (pad, pad)
    ap = np.pad(a, pw, mode="constant")
    fa = np.fft.rfft(ap, size, axis=axis)
    out = np.fft.irfft(fa * fk.reshape([-1 if i == axis else 1 for i in range(a.ndim)]), size, axis=axis)
    sl = [slice(None)] * a.ndim
    sl[axis] = slice(2 * pad, 2 * pad + n)
    return out[tuple(sl)]


def blur(a, sigma):
    """A Gaussian blur over the first two axes, `sigma` pixels."""
    if sigma < 0.3:
        return a
    return _blur1(_blur1(a, sigma, 0), sigma, 1)


def grid(w, h):
    """Pixel centres, x right and y down, scaled so the long side runs -1 to 1."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    s = max(w, h) / 2
    return (xs + 0.5 - w / 2) / s, (ys + 0.5 - h / 2) / s


def save(path, rgb, alpha, size):
    """Downsamples (premultiplied, Lanczos) to `size` on the long side and writes RGBA."""
    rgb = np.clip(rgb, 0, 1)
    a = np.clip(alpha, 0, 1)
    h, w = a.shape
    s = size / max(w, h)
    ow, oh = max(1, round(w * s)), max(1, round(h * s))
    chans = [Image.fromarray((rgb[..., i] * a).astype(np.float32), "F") for i in range(3)]
    chans.append(Image.fromarray(a.astype(np.float32), "F"))
    out = [np.asarray(c.resize((ow, oh), Image.LANCZOS)) for c in chans]
    A = np.clip(out[3], 0, 1)
    rgbp = np.stack(out[:3], -1)
    rgbo = np.where(A[..., None] > 1e-4, rgbp / np.maximum(A, 1e-4)[..., None], 0)
    img = np.dstack([np.clip(rgbo, 0, 1) * 255, A * 255]).round().astype(np.uint8)
    Image.fromarray(img, "RGBA").save(path, optimize=True)
    print("wrote", os.path.basename(path), f"{ow}x{oh}")
