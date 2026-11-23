"""A star seen from inside its planetary system: a limb-darkened, granulated disc that
burns out to white, a faint corona with streamers, a wide soft glare and short spikes.
The disc fills about a tenth of the picture so the glare has room to fall off."""
import numpy as np

from common import Perlin3, blackbody, blur, fbm, grid, smooth, tonemap


def render(w, h, seed=31, temp=5600.0, disc=0.11, exposure=1.0):
    n = Perlin3(seed)
    x, y = grid(w, h)
    r = np.hypot(x, y)
    rr = r / disc
    col = blackbody(temp)
    mu = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    # Limb darkening (redder at the limb), granulation and a few spots.
    limb = 0.35 + 0.65 * mu
    gran = 0.9 + 0.2 * fbm(n, x / disc * 18, y / disc * 18, 0.4, 4)
    spots = 1 - 0.6 * smooth(0.74, 0.8, fbm(n, x / disc * 3, y / disc * 3, 2.2, 4)) * smooth(1.0, 0.7, rr)
    surf = (rr < 1) * limb * gran * spots * 40
    limb_col = blackbody(temp * (0.75 + 0.25 * mu))
    light = surf[..., None] * (0.55 * limb_col + 0.45)
    # Corona: falls off fast, with streamers.
    ang = np.arctan2(y, x)
    streak = 0.6 + 0.8 * fbm(n, np.cos(ang) * 4, np.sin(ang) * 4, 0.1, 4) ** 2
    corona = (rr >= 0.98) * np.clip(rr, 1, None) ** -4.5 * streak * 3
    light = light + corona[..., None] * blackbody(temp * 1.2)
    # Glare: the eye's (or lens's) scatter, wide and soft, and a bloom.
    glare = 1.2 / (1 + (r / (disc * 0.9)) ** 2.6) + 0.05 * np.exp(-r / 0.22)
    light = light + glare[..., None] * col
    s = w / 1024
    for a in (0.0, np.pi / 2, np.pi / 4, -np.pi / 4):
        along = x * np.cos(a) + y * np.sin(a)
        across = -x * np.sin(a) + y * np.cos(a)
        k = 1.0 if a in (0.0, np.pi / 2) else 0.35
        light = light + (k * 0.8 * np.exp(-(across * w / 2) ** 2 / (2 * (1.2 * s) ** 2))
                         * np.exp(-np.abs(along) / 0.22) * (r > disc * 0.9))[..., None] * col
    lum = light * exposure
    rgb = tonemap(lum + blur(lum, w / 200) * 0.2)
    alpha = np.clip(np.max(rgb, -1) * 1.3, 0, 1) * smooth(0.98, 0.55, r)
    out = np.where(alpha[..., None] > 1e-4, rgb / np.maximum(alpha, 1e-4)[..., None], 0)
    return np.clip(out, 0, 1), alpha
