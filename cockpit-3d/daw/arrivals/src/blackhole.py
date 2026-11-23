"""A black hole and its accretion disc, ray traced through a Schwarzschild metric.

Each pixel's light is followed backwards from the camera as a null geodesic (in units of
the Schwarzschild radius, r_s = 1, the orbit obeys x'' = -1.5 h^2 x / r^5, with h the
conserved angular momentum per unit speed), crossing a thin disc from the innermost
stable orbit (3 r_s) outwards as often as it bends round. Each crossing adds the disc's
light, shifted by its orbital Doppler factor and gravitational redshift (g^4 in
brightness, g in temperature), so the side turning toward the camera is bright and blue
white and the far side dim and red; the disc's far side shows bent up over the shadow, and
higher-order images make the thin photon ring at the shadow's edge.
"""
import numpy as np

from common import Perlin3, blackbody, fbm, tonemap, blur


def render(w, h, seed=25, elevation_deg=6.0, dist=34.0, half_fov_deg=19.0, roll_deg=-8.0,
           r_in=3.0, r_out=14.0, exposure=2.2):
    noise = Perlin3(seed)
    e = np.radians(elevation_deg)
    O = dist * np.array([0.0, np.sin(e), np.cos(e)])
    f = -O / np.linalg.norm(O)
    right = np.cross(f, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    rr = np.radians(roll_deg)
    right, up = right * np.cos(rr) + up * np.sin(rr), up * np.cos(rr) - right * np.sin(rr)
    s = np.tan(np.radians(half_fov_deg))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    px = (xs + 0.5 - w / 2) / (w / 2) * s
    py = -(ys + 0.5 - h / 2) / (w / 2) * s
    d = f[None, None, :] + px[..., None] * right + py[..., None] * up
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    n = w * h
    pos = np.broadcast_to(O, (n, 3)).copy()
    vel = d.reshape(n, 3).copy()
    h2 = np.sum(np.cross(pos, vel) ** 2, axis=1)

    col = np.zeros((n, 3))
    trans = np.ones(n)
    captured = np.zeros(n, bool)
    active = np.arange(n)

    def acc(p, h2a):
        r2 = np.sum(p * p, axis=1)
        return -1.5 * h2a[:, None] * p / (r2 ** 2.5)[:, None]

    for step in range(4000):
        if active.size == 0:
            break
        p, v, hh = pos[active], vel[active], h2[active]
        r = np.linalg.norm(p, axis=1)
        dt = np.clip(0.06 * r, 0.004, 1.5)[:, None]
        # RK4
        k1v = acc(p, hh); k1x = v
        k2v = acc(p + 0.5 * dt * k1x, hh); k2x = v + 0.5 * dt * k1v
        k3v = acc(p + 0.5 * dt * k2x, hh); k3x = v + 0.5 * dt * k2v
        k4v = acc(p + dt * k3x, hh); k4x = v + dt * k3v
        np_ = p + dt / 6 * (k1x + 2 * k2x + 2 * k3x + k4x)
        nv = v + dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v)
        # Disc crossings: y changes sign.
        cross = (p[:, 1] * np_[:, 1]) < 0
        if cross.any():
            t = p[cross, 1] / (p[cross, 1] - np_[cross, 1])
            P = p[cross] + t[:, None] * (np_[cross] - p[cross])
            rh = np.hypot(P[:, 0], P[:, 2])
            on = (rh > r_in) & (rh < r_out)
            if on.any():
                idx = active[cross][on]
                P, rh = P[on], rh[on]
                dvec = nv[cross][on]
                dvec = dvec / np.linalg.norm(dvec, axis=1, keepdims=True)
                # Keplerian orbit, counter-clockwise seen from above.
                vdir = np.stack([P[:, 2], np.zeros_like(rh), -P[:, 0]], 1) / rh[:, None]
                beta = np.sqrt(0.5 / (rh - 1.0))
                gamma = 1 / np.sqrt(1 - beta ** 2)
                cos_t = np.sum(vdir * -dvec, axis=1)
                g = np.sqrt(1 - 1 / rh) / (gamma * (1 - beta * cos_t))
                # Thin-disc temperature profile, peaked just outside the inner edge.
                prof = rh ** -0.75 * np.clip(1 - np.sqrt(r_in / rh), 0, 1) ** 0.25
                prof /= 0.488 * r_in ** -0.75  # ~1 at its peak
                phi = np.arctan2(P[:, 2], P[:, 0])
                # Streaks wound along the orbit: noise in (log r, phi + twist).
                lr = np.log(rh)
                tw = phi + 2.5 * lr
                tex = fbm(noise, np.cos(tw) * 2.0 + lr * 9, np.sin(tw) * 2.0, lr * 22, 5)
                tex = 0.45 + 1.1 * np.clip(tex, 0, 1) ** 1.6
                fade = np.clip((r_out - rh) / 5, 0, 1) ** 1.5
                temp = 4300.0 * prof * g
                emit = blackbody(temp) * ((prof ** 4) * g ** 4 * tex * fade)[:, None]
                opac = (0.97 * np.clip(1.2 - (rh - r_in) / (r_out - r_in), 0.25, 1) * fade)
                col[idx] += trans[idx, None] * emit * 1.0
                trans[idx] *= 1 - opac * np.clip(tex / 1.2, 0.3, 1)
        pos[active], vel[active] = np_, nv
        rn = np.linalg.norm(np_, axis=1)
        gone = rn < 1.0005
        captured[active[gone]] = True
        away = (rn > dist * 1.3) & (np.sum(np_ * nv, axis=1) > 0)
        dim = trans[active] < 0.002
        keep = ~(gone | away | dim)
        active = active[keep]

    col = col.reshape(h, w, 3)
    trans = trans.reshape(h, w)
    captured = captured.reshape(h, w)
    alpha = 1 - trans
    alpha = np.where(captured, 1.0, alpha)
    # A soft glow from the brightest light, and tonemapping.
    lum = col * exposure
    glow = blur(lum, w / 90) * 0.35 + blur(lum, w / 25) * 0.15
    rgb = tonemap(lum + glow)
    # A little more saturation, as a long exposure of hot gas reads.
    grey = rgb.mean(axis=-1, keepdims=True)
    rgb = np.clip(grey + (rgb - grey) * 1.35, 0, 1)
    ga = np.clip(np.max(tonemap(glow), axis=-1) * 1.6, 0, 1)
    alpha = np.maximum(alpha, ga)
    # Keep the colour where only glow shows (unpremultiplied).
    return rgb, alpha
