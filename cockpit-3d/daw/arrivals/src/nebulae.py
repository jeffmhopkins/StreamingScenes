"""Deep-sky pictures: two nebulae, a spiral galaxy and a planetary (ring) nebula.

Each is built as light and dust: emission in layers of warped, ridged noise (each layer its
own gas, colour and scale), dust that absorbs both the emission and the stars behind it, and
young stars inside with soft glows and diffraction spikes. Alpha is the light plus the dust,
so the sky behind shows through thin gas and is blotted out by thick dust.
"""
import numpy as np

from common import Perlin3, blur, fbm, grid, ramp, ridged, smooth, tonemap, warp


def _stars(w, h, seed, count, weight=None, bright=1.0, spikes=0, colour_spread=1.0):
    """HDR star light: points with a soft core and a halo; the brightest `spikes` get
    four diffraction spikes. `weight` (h, w) biases where they fall."""
    r = np.random.default_rng(seed)
    img = np.zeros((h, w, 3))
    if weight is not None:
        p = weight.ravel() / weight.sum()
        idx = r.choice(w * h, count, p=p)
        ys, xs = np.divmod(idx, w)
        xs = xs + r.random(count)
        ys = ys + r.random(count)
    else:
        xs, ys = r.random(count) * w, r.random(count) * h
    mag = r.pareto(1.6, count) + 0.3
    mag = mag / mag.max()
    order = np.argsort(-mag)
    # Colour: mostly white-blue for young stars, some yellow and orange.
    t = r.random(count)
    cols = np.where(t[:, None] < 0.6 * colour_spread, [0.75, 0.85, 1.0],
                    np.where(t[:, None] < 0.85, [1.0, 0.95, 0.85], [1.0, 0.72, 0.5]))
    s = w / 1024
    for k, i in enumerate(order):
        a = mag[i] * bright
        rad = (0.7 + 2.2 * a ** 0.5) * s
        box = int(max(3, rad * 6 + (a * 60 * s if k < spikes else 0)))
        x0, y0 = int(xs[i]), int(ys[i])
        xa, xb = max(0, x0 - box), min(w, x0 + box + 1)
        ya, yb = max(0, y0 - box), min(h, y0 + box + 1)
        if xa >= xb or ya >= yb:
            continue
        yy, xx = np.mgrid[ya:yb, xa:xb]
        dx, dy = xx + 0.5 - xs[i], yy + 0.5 - ys[i]
        d2 = dx * dx + dy * dy
        prof = 6 * a * np.exp(-d2 / (2 * (0.6 * rad) ** 2)) + 0.5 * a * np.exp(-np.sqrt(d2) / (rad * 2.5))
        if k < spikes:
            L = a * 70 * s
            for ux, uy in ((1, 0.08), (-0.08, 1)):
                along = dx * ux + dy * uy
                across = dx * -uy + dy * ux
                prof = prof + 1.4 * a * np.exp(-across ** 2 / (2 * (0.45 * s) ** 2)) * np.exp(-np.abs(along) / (L * 0.35))
        img[ya:yb, xa:xb] += prof[..., None] * cols[i]
    return img


def _finish(light, dust, w, exposure=1.0, sat=1.1, edge=None):
    """Light (HDR) through dust (0..1 opacity) to an unpremultiplied RGB and alpha."""
    lum = light * exposure
    glow = blur(lum, w / 160) * 0.25
    rgb = tonemap(lum + glow)
    grey = rgb.mean(axis=-1, keepdims=True)
    rgb = np.clip(grey + (rgb - grey) * sat, 0, 1)
    a_light = np.clip(np.max(rgb, axis=-1) * 1.25, 0, 1)
    alpha = 1 - (1 - a_light) * (1 - dust)
    if edge is not None:
        alpha = alpha * edge
    # Unpremultiply: the light is what shows over black, so colour = rgb / alpha.
    out = np.where(alpha[..., None] > 1e-4, rgb / np.maximum(alpha, 1e-4)[..., None], 0)
    return np.clip(out, 0, 1), np.clip(alpha, 0, 1)


def _edge(x, y, rx=1.0, ry=1.0, soft=0.35, seed=5):
    n = Perlin3(seed)
    d = np.sqrt((x / rx) ** 2 + (y / ry) ** 2) + 0.25 * (fbm(n, x * 2.5, y * 2.5, 0.0, 5) - 0.5)
    return smooth(1.0, 1.0 - soft, d)


def emission_nebula(w, h, seed=21):
    """A star-forming cloud: hydrogen red, sulphur deep red and oxygen teal in separate
    layers, bright rims where the young stars eat into it, and dark pillars of dust."""
    n = Perlin3(seed)
    x, y = grid(w, h)
    wx, wy, wz = warp(n, x * 1.6, y * 1.6, 0.3, 1.1, 5)
    wx2, wy2, wz2 = warp(n, wx * 1.8 + 4, wy * 1.8, wz, 0.6, 4)
    body = fbm(n, wx, wy, wz, 8)
    shape = smooth(0.95, 0.15, np.hypot(x * 0.95 + 0.08, y * 1.25 - 0.05) + 0.35 * (fbm(n, x * 1.2, y * 1.2, 5.5, 4) - 0.5))
    ha = smooth(0.40, 0.85, body) * shape
    fil = ridged(n, wx2 * 2.2, wy2 * 2.2, wz2, 7)
    ha = ha * (0.35 + 1.3 * fil ** 2)
    sii = smooth(0.5, 0.9, fbm(n, wx2 * 1.4 + 9, wy2 * 1.4, 2.0, 6)) * shape * fil
    # Oxygen glows in the hot cavity round the cluster.
    cx, cy = 0.08, -0.04
    rc = np.hypot(x - cx, y - cy)
    oiii = smooth(0.32, 0.0, rc) * smooth(0.45, 0.75, fbm(n, wx * 2.5, wy * 2.5, 7.0, 6)) * shape
    # Bright ionisation fronts: where the cloud faces the cluster.
    rim = smooth(0.62, 0.78, body) * smooth(0.82, 0.62, body) * smooth(0.75, 0.15, rc)
    light = (ha[..., None] * np.array([1.0, 0.2, 0.26]) * 2.2
             + sii[..., None] * np.array([0.85, 0.05, 0.10]) * 0.9
             + oiii[..., None] * np.array([0.30, 0.80, 0.78]) * 0.7
             + rim[..., None] * np.array([1.0, 0.75, 0.55]) * 1.6
             + (ha ** 2)[..., None] * np.array([1.0, 0.55, 0.55]) * 1.2)
    # Dust: pillars pointing at the cluster, and lanes, dark and slightly brown-lit.
    ang = np.arctan2(y - cy, x - cx)
    pill = fbm(n, np.cos(ang) * 3 + rc * 0.8, np.sin(ang) * 3, rc * 7, 6)
    dust = smooth(0.56, 0.72, pill) * smooth(0.18, 0.5, rc)
    lanes = smooth(0.58, 0.75, fbm(n, wx * 1.3 + 20, wy * 1.3, 3.3, 7))
    dust = np.clip(np.maximum(dust, lanes * 0.85) * shape * 1.1, 0, 0.95)
    edge_lit = blur(rim, w / 300) * dust
    light = light * (1 - dust[..., None] * 0.92) + edge_lit[..., None] * np.array([1.0, 0.5, 0.35]) * 2.5
    wt = smooth(0.4, 0.0, rc) * 30 + shape * 2 + 0.2
    stars = _stars(w, h, seed + 1, 260, weight=wt, bright=1.6, spikes=8)
    light = light + stars * (1 - dust[..., None] * 0.8)
    return _finish(light, dust * 0.9, w, exposure=1.7, sat=1.15, edge=_edge(x, y, 1.0, 0.72, 0.4))


def blue_nebula(w, h, seed=22):
    """A reflection nebula: blue starlight scattered by fine dust round a few bright young
    stars, with wisps combed out by their wind and darker, brown lanes of thicker dust."""
    n = Perlin3(seed)
    x, y = grid(w, h)
    wx, wy, wz = warp(n, x * 1.3, y * 1.3, 1.7, 0.9, 5)
    # Wisps: stretched noise along a gentle flow.
    flow = 0.6 + 0.4 * np.sin(x * 1.5 + y * 0.6)
    wisp = fbm(n, wx * 1.2, wy * 4.0 * flow, wz, 8)
    fine = ridged(n, wx * 3, wy * 7, wz + 2, 6)
    body = smooth(0.38, 0.8, fbm(n, wx, wy, wz, 7))
    shape = smooth(0.95, 0.2, np.hypot(x * 0.9, y * 1.3) + 0.3 * (fbm(n, x, y, 9.9, 4) - 0.5))
    # Illuminated by stars: falls off with distance from each.
    srcs = [(-0.12, -0.05, 1.0), (0.22, 0.12, 0.6), (-0.38, 0.18, 0.35)]
    illum = sum(b / (0.02 + 6 * ((x - sx) ** 2 + (y - sy) ** 2)) for sx, sy, b in srcs) + 0.25
    dens = body * (0.35 + 1.4 * (wisp * fine) ** 1.3) * shape
    blue = dens * illum
    light = blue[..., None] * np.array([0.30, 0.52, 1.0]) * 0.55
    # Near the stars the scattering whitens.
    light = light + (dens * illum ** 2 * 0.004)[..., None] * np.array([0.8, 0.9, 1.0])
    # A faint warm hydrogen layer behind.
    ha = smooth(0.55, 0.85, fbm(n, wx * 0.8 + 30, wy * 0.8, 4.2, 6)) * shape * 0.25
    light = light + ha[..., None] * np.array([0.9, 0.3, 0.35])
    lanes = smooth(0.6, 0.78, fbm(n, wx * 1.6 + 11, wy * 2.2, 6.6, 7)) * shape
    dust = np.clip(lanes * 1.1, 0, 0.9)
    light = light * (1 - dust[..., None] * 0.85) + (dust * blur(blue, w / 200) * 0.25)[..., None] * np.array([0.7, 0.45, 0.3])
    stars = _stars(w, h, seed + 1, 70, weight=shape + 0.2, bright=0.8, spikes=0)
    for sx, sy, b in srcs:
        px, py = (sx * w / 2 + w / 2), (sy * w / 2 + h / 2)
        stars = stars + _one_star(w, h, px, py, b * 4, (0.8, 0.88, 1.0))
    light = light + stars * (1 - dust[..., None] * 0.8)
    return _finish(light, dust * 0.85, w, exposure=1.6, sat=1.0, edge=_edge(x, y, 1.0, 0.72, 0.4))


def _one_star(w, h, px, py, a, col):
    s = w / 1024
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = xx + 0.5 - px, yy + 0.5 - py
    d2 = dx * dx + dy * dy
    prof = a * (4 * np.exp(-d2 / (2 * (1.8 * s) ** 2)) + 0.6 * np.exp(-np.sqrt(d2) / (9 * s))
                + 0.15 * np.exp(-np.sqrt(d2) / (40 * s)))
    L = 22 * s * a ** 0.5
    for ux, uy in ((1, 0.05), (-0.05, 1)):
        along = dx * ux + dy * uy
        across = dx * -uy + dy * ux
        prof = prof + a * 0.5 * np.exp(-across ** 2 / (2 * (0.5 * s) ** 2)) * np.exp(-np.abs(along) / L)
    return prof[..., None] * np.array(col)


def spiral_galaxy(w, h, seed=23, incl_deg=58.0, pa_deg=-28.0):
    """A barred spiral seen at an angle: a yellow bulge and bar, blue arms beaded with pink
    star-forming knots, dust lanes on the arms' inner edges, all in the tilted disc."""
    n = Perlin3(seed)
    x, y = grid(w, h)
    pa, inc = np.radians(pa_deg), np.radians(incl_deg)
    # Picture to disc coordinates.
    u = x * np.cos(pa) + y * np.sin(pa)
    v = (-x * np.sin(pa) + y * np.cos(pa)) / np.cos(inc)
    u, v = u * 1.12, v * 1.12
    r = np.hypot(u, v)
    th = np.arctan2(v, u)
    k = 1 / np.tan(np.radians(16))  # pitch angle
    arms = 2
    ph = th - k * np.log(np.maximum(r, 0.05) / 0.25)
    wv = fbm(n, u * 3, v * 3, 0.5, 5)
    arm = 0.5 + 0.5 * np.cos(arms * ph + 1.4 * (wv - 0.5))
    arm_sharp = arm ** 3
    disc = np.exp(-r / 0.32) * smooth(1.25, 0.7, r)
    clump = fbm(n, u * 9, v * 9, 1.1, 6)
    arm_l = disc * (0.2 + 1.8 * arm_sharp * (0.2 + clump ** 2 * 1.6)) * smooth(0.12, 0.3, r)
    # Bulge and a short bar.
    bar = np.exp(-((u * np.cos(0.5) + v * np.sin(0.5)) / 0.22) ** 2 - ((-u * np.sin(0.5) + v * np.cos(0.5)) / 0.07) ** 2)
    bulge = np.exp(-r / 0.035) * 3.0 + np.exp(-r / 0.1) * 0.45
    light = (bulge + bar * 0.35)[..., None] * np.array([1.0, 0.82, 0.6]) \
        + arm_l[..., None] * np.array([0.55, 0.7, 1.0]) * 1.1
    # Pink HII knots strung along the arms.
    knots = smooth(0.62, 0.8, fbm(n, u * 22, v * 22, 3.3, 3)) * arm_sharp * disc * smooth(0.2, 0.4, r)
    light = light + knots[..., None] * np.array([1.0, 0.35, 0.55]) * 2.5
    # Dust on the inner (trailing) edge of each arm, and the near side's lanes darker (tilt).
    lane = 0.5 + 0.5 * np.cos(arms * ph + 1.4 * (wv - 0.5) + 0.7)
    dust = smooth(0.85, 0.99, lane) * np.exp(-r / 0.45) * 1.4 * smooth(0.35, 0.75, fbm(n, u * 14, v * 14, 7.7, 5))
    near = smooth(-0.2, 0.4, -(-x * np.sin(pa) + y * np.cos(pa)))  # one side of the minor axis
    dust = np.clip(dust * (0.6 + 0.6 * near), 0, 0.75) * smooth(0.1, 0.25, r)
    light = light * (1 - dust[..., None] * 0.9)
    # A faint outer halo of old stars, and a few foreground stars.
    light = light + (np.exp(-np.hypot(x, y * 1.2) / 0.35) * 0.08)[..., None] * np.array([1.0, 0.9, 0.75])
    stars = _stars(w, h, seed + 1, 60, bright=0.6, spikes=2, colour_spread=0.6)
    sm = _stars(w, h, seed + 2, 400, weight=arm_l + 1e-4, bright=0.12, spikes=0)
    light = light + stars + sm
    edge = smooth(1.0, 0.75, np.hypot(x, y * 1.15))
    return _finish(light, dust * 0.6 * smooth(0.95, 0.5, r), w, exposure=1.5, sat=1.15, edge=edge)


def ring_nebula(w, h, seed=24):
    """A planetary nebula: a dying star's shed shell, seen down its axis as a ring. Oxygen
    teal fills the inside, hydrogen and nitrogen red rim the outside in knotted filaments,
    and a faint, looser halo lies beyond. The hot white dwarf sits in the middle."""
    n = Perlin3(seed)
    x, y = grid(w, h)
    rot = np.radians(25)
    u = x * np.cos(rot) + y * np.sin(rot)
    v = (-x * np.sin(rot) + y * np.cos(rot)) * 1.3
    ang = np.arctan2(v, u)
    jit = 0.06 * (fbm(n, np.cos(ang) * 2, np.sin(ang) * 2, 0.5, 5) - 0.5)
    r = np.hypot(u, v) + jit
    R = 0.42
    # Projected thick shell: brightest just inside its outer edge.
    shell = np.clip(np.sqrt(np.maximum(R ** 2 - r ** 2, 0)) - np.sqrt(np.maximum((R * 0.62) ** 2 - r ** 2, 0)), 0, None) / (R * 0.75)
    fil = ridged(n, u * 9, v * 9, 1.3, 6)
    knots = ridged(n, np.cos(ang) * 6 + r * 30, np.sin(ang) * 6, r * 12, 5)
    oiii = smooth(R * 0.95, R * 0.3, r) * (0.25 + 1.1 * fbm(n, u * 6, v * 6, 2.2, 7) ** 2) * (0.3 + 0.9 * smooth(0, R * 0.85, r))
    red = shell * (0.15 + 1.6 * knots ** 3) * smooth(R * 0.7, R * 0.92, r) * (0.6 + 0.6 * fil)
    halo = smooth(R * 2.3, R * 1.0, r) * smooth(R * 0.8, R * 1.05, r) * (0.3 + 0.7 * fil) * 0.4
    light = (oiii[..., None] * np.array([0.25, 0.85, 0.85]) * 0.9
             + (shell * 0.35)[..., None] * np.array([0.9, 0.9, 0.6]) * smooth(R * 0.9, R * 0.5, r)[..., None]
             + red[..., None] * np.array([1.0, 0.25, 0.2]) * 1.8
             + halo[..., None] * np.array([0.9, 0.3, 0.4]))
    # Dark knots (cometary globules) on the inner rim.
    glob = smooth(0.72, 0.85, ridged(n, u * 26, v * 26, 4.4, 3)) * smooth(R * 0.6, R * 0.8, r) * smooth(R * 0.95, R * 0.8, r)
    dust = np.clip(glob * 0.7, 0, 0.8)
    light = light * (1 - dust[..., None])
    # Hazy rather than crisp: the shell's light spread wide, so its rim melts into the
    # halo and the sky instead of drawing a hard line.
    light = light * 0.5 + blur(light, w / 70) * 0.75
    light = light + _one_star(w, h, w / 2, h / 2, 1.2, (0.85, 0.9, 1.0))
    light = light + _stars(w, h, seed + 1, 40, bright=0.5, spikes=1)
    return _finish(light, dust * 0.5, w, exposure=1.5, sat=1.1, edge=_edge(x, y, 0.98, 0.98, 0.3))
