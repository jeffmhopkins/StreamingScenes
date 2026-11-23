"""Planets and moons, drawn as lit spheres in 3D: an orthographic view of a unit sphere,
its surface textured in the planet's own frame (tilted on its axis), bump-lit from a
height field, with an atmosphere that scatters blue at the lit limb and red at the
terminator and glows past the edge, clouds that cast shadows, a sun glint on oceans,
city lights on the night side, and rings that the planet shadows and that shadow it."""
import numpy as np

from common import Perlin3, blur, fbm, grid, mix, ramp, ridged, smooth, tonemap, warp


def rot(axis_tilt_deg, spin_deg=0.0, lean_deg=0.0):
    """The planet's frame in view space: spun about its pole, the pole tipped toward the
    viewer by `axis_tilt_deg` and leaned in the picture by `lean_deg`."""
    a, b, c = (np.radians(v) for v in (spin_deg, axis_tilt_deg, lean_deg))
    Ry = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(b), -np.sin(b)], [0, np.sin(b), np.cos(b)]])
    Rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def render(w, h, surface, light, radius=0.78, center=(0.0, 0.0), frame=None, atmo=None,
           clouds=None, night=None, rings=None, bump=1.0, spec=None, exposure=1.6,
           wrap=0.0):
    """`surface(q)` gives (albedo rgb, height, extra) for points q (..., 3) on the unit
    sphere in the planet's frame. `atmo` is (rgb, thickness in radii, strength).
    `clouds(q)` gives cover 0..1. `night(q)` gives emitted rgb on the dark side.
    `rings` is (inner, outer, density(r), colour(r)). `spec(q)` is a gloss mask."""
    frame = np.eye(3) if frame is None else frame
    L = np.array(light, np.float64)
    L /= np.linalg.norm(L)
    gx, gy = grid(w, h)
    x = (gx - center[0]) / radius
    y = -(gy - center[1]) / radius  # y up in view space
    r2 = x * x + y * y
    disc = r2 <= 1.0
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    N = np.stack([x, y, z], -1)
    q = N @ frame  # view to planet frame (frame is orthonormal: inverse = transpose)
    px = 2.0 / (max(w, h) * radius)  # one pixel in sphere units

    albedo, height, extra = surface(q)
    # Bump: tilt the normal against the height field's slope in the picture.
    if bump:
        hy, hx = np.gradient(height)
        k = bump / px * 0.0025
        Nb = N + np.stack([-hx * k, hy * k, np.zeros_like(hx)], -1)
        Nb /= np.linalg.norm(Nb, axis=-1, keepdims=True)
    else:
        Nb = N
    ndl = np.sum(Nb * L, -1)
    ndl_s = np.sum(N * L, -1)
    diffuse = np.clip((ndl + wrap) / (1 + wrap), 0, 1)
    # A soft terminator: no light past the geometric one.
    diffuse *= smooth(-0.04, 0.12, ndl_s)
    col = albedo * diffuse[..., None]

    if clouds is not None:
        c = clouds(q)
        # The cloud's shadow on the ground, offset away from the light.
        Lq = L @ frame
        shadow = clouds(q - Lq * 0.012)
        col = col * (1 - 0.6 * shadow * smooth(0, 0.2, ndl_s))[..., None]
        cl = np.clip(ndl_s + 0.05, 0, 1) ** 0.8
        col = mix(col, (np.array([0.97, 0.97, 1.0]) * cl[..., None]), c)

    if spec is not None:
        gloss = spec(q)
        if clouds is not None:
            gloss = gloss * (1 - c)
        H = L + np.array([0, 0, 1.0])
        H /= np.linalg.norm(H)
        sp = np.clip(np.sum(Nb * H, -1), 0, 1) ** 300 * 1.5 + np.clip(np.sum(Nb * H, -1), 0, 1) ** 30 * 0.12
        col = col + (sp * gloss * (ndl_s > 0))[..., None] * np.array([1.0, 0.95, 0.85])

    if night is not None:
        dark = smooth(0.05, -0.15, ndl_s)
        em = night(q)
        if clouds is not None:
            em = em * (1 - 0.8 * c)[..., None]
        col = col + em * dark[..., None]

    if extra is not None:  # emission (lava)
        col = col + extra

    alpha = np.clip((1 - np.sqrt(r2)) / px + 0.5, 0, 1)

    # Rings: in the planet's equatorial plane.
    if rings is not None:
        rin, rout, dens_f, col_f = rings
        n = frame @ np.array([0, 1.0, 0])  # ring normal (planet's pole) in view space
        # Where each pixel's view ray (along -z) meets the ring plane.
        t_ok = abs(n[2]) > 1e-6
        zr = -(n[0] * x + n[1] * y) / n[2]
        P = np.stack([x, y, zr], -1)
        rr = np.linalg.norm(P, axis=-1)
        rd = dens_f(rr) * ((rr > rin) & (rr < rout))
        # The planet's shadow on the ring: the ray from the ring point to the sun meets the sphere.
        pl = np.sum(P * L, -1)
        perp2 = rr ** 2 - pl ** 2
        in_shadow = (pl < 0) & (perp2 < 1)
        ring_lit = np.where(in_shadow, 0.04, 1.0)
        # Lit from above or below: the unlit face is dimmer, lit by light through it.
        face = abs(np.dot(n, L))
        rc = col_f(rr) * (ring_lit * (0.3 + 1.1 * face))[..., None]
        front = (zr > z) | ~disc
        # The ring's shadow on the planet: from the surface point toward the sun.
        s = -(np.sum(N * n, -1)) / np.dot(L, n) if abs(np.dot(L, n)) > 1e-6 else np.full(x.shape, -1.0)
        Q = N + s[..., None] * L
        qr = np.linalg.norm(Q, axis=-1)
        rshadow = np.where((s > 0) & disc, dens_f(qr) * ((qr > rin) & (qr < rout)), 0)
        col = col * (1 - 0.85 * rshadow)[..., None]
        ra = np.clip(rd, 0, 1)
        behind = ~front & disc
        ra_front = np.where(behind, 0, ra)
        # Ring behind the planet is hidden; the ring in front lies over it.
        col = col * alpha[..., None]
        col = col * (1 - ra_front[..., None]) + rc * ra_front[..., None]
        alpha = alpha * (1 - ra_front) + ra_front
        col = np.where(alpha[..., None] > 1e-6, col / np.maximum(alpha, 1e-6)[..., None], 0)

    if atmo is not None:
        acol, thick, strength = atmo
        acol = np.array(acol)
        rad = np.sqrt(r2)
        # Inside the disc: in-scatter along the view ray grows toward the limb; lit by the sun,
        # reddened near the terminator.
        mu = np.clip(z, 0, 1)
        path = np.clip(1 / np.maximum(mu, 0.05) - 1, 0, 12) * thick
        sun = smooth(-0.25, 0.35, ndl_s)
        sunset = smooth(0.25, -0.05, ndl_s) * smooth(-0.3, 0.0, ndl_s)
        scat = 1 - np.exp(-path * 3)
        tint = mix(acol, np.array([1.0, 0.45, 0.2]), sunset * 0.45)
        col = col * (1 - 0.35 * scat * sun)[..., None] + tint * (scat * sun * strength)[..., None]
        # Outside: a glowing shell fading over `thick`, brighter on the lit side, with forward
        # scatter where the sun is behind.
        out = (rad > 1) & (rad < 1 + thick * 4)
        hgt = (rad - 1) / thick
        dens = np.exp(-hgt * 1.6) * smooth(1 + thick * 4, 1 + thick * 2, rad)
        rdir = np.stack([x, y, np.zeros_like(x)], -1) / np.maximum(rad, 1e-6)[..., None]
        lit = smooth(-0.35, 0.5, np.sum(rdir * L, -1)) + 0.6 * np.clip(-L[2], 0, 1)
        glow = dens * lit * strength * 1.2
        halo_col = acol[None, None, :] * glow[..., None]
        ha = np.clip(glow * 1.1, 0, 1)
        col = np.where(out[..., None] & (alpha < 1)[..., None],
                       (col * alpha[..., None] + halo_col) / np.maximum(alpha + ha * (1 - alpha), 1e-6)[..., None], col)
        alpha = np.where(out, alpha + ha * (1 - alpha), alpha)

    rgb = tonemap(col * exposure)
    return rgb, alpha


# ---- surfaces ----
def terran(seed):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        wx, wy, wz = warp(n, x * 1.6, y * 1.6, z * 1.6, 0.6)
        h = fbm(n, wx, wy, wz, 9)
        mount = ridged(n, x * 5, y * 5, z * 5, 6)
        land = smooth(0.505, 0.52, h)
        elev = np.clip((h - 0.52) * 6, 0, 1)
        lat = np.abs(y)
        dry = fbm(n, x * 3 + 4, y * 3, z * 3, 5)
        green = ramp(dry, [(0, (0.10, 0.22, 0.07)), (0.5, (0.22, 0.30, 0.10)), (0.65, (0.52, 0.42, 0.24)), (1, (0.70, 0.58, 0.40))])
        desert_belt = smooth(0.12, 0.3, 0.32 - np.abs(lat - 0.33))
        ground = mix(green, np.array([0.78, 0.62, 0.40]), desert_belt * 0.7)
        ground = mix(ground, np.array([0.45, 0.40, 0.36]), smooth(0.3, 0.8, elev) * mount)
        depth = np.clip((0.52 - h) * 5, 0, 1)
        ocean = mix(np.array([0.05, 0.22, 0.38]), np.array([0.01, 0.04, 0.14]), depth)
        col = mix(ocean, ground, land)
        ice = smooth(0.78, 0.86, lat + 0.08 * (fbm(n, x * 6, y * 6, z * 6, 4) - 0.5) + 0.05 * elev)
        col = mix(col, np.array([0.93, 0.95, 0.98]), ice)
        height = land * (elev * 0.6 + mount * 0.4 * elev) + ice * 0.05
        return col, height, None
    return f, (lambda q: 1 - smooth(0.5, 0.52, fbm(n, *warp(n, q[..., 0] * 1.6, q[..., 1] * 1.6, q[..., 2] * 1.6, 0.6), 9)))


def cloud_layer(seed, cover=0.52, scale=2.6):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        # Bands of weather by latitude, sheared into swirls.
        shear = np.sin(y * 9) * 0.35
        wx, wy, wz = warp(n, x * scale + shear, y * scale * 1.8, z * scale - shear, 0.9, 5)
        c = fbm(n, wx, wy, wz, 8)
        c = smooth(cover, cover + 0.16, c) * (0.6 + 0.4 * fbm(n, x * 9, y * 14, z * 9, 4))
        return np.clip(c, 0, 0.97)
    return f


def city_lights(seed, land_mask):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        pop = smooth(0.6, 0.75, fbm(n, x * 7, y * 7, z * 7, 6)) * smooth(0.45, 0.7, fbm(n, x * 40, y * 40, z * 40, 3))
        pop = pop * (1 - land_mask(q)) * smooth(0.75, 0.6, np.abs(y))
        return pop[..., None] * np.array([1.0, 0.72, 0.38]) * 0.9
    return f


def cratered(seed, base=(0.62, 0.60, 0.58), mare=(0.32, 0.31, 0.31), count=260):
    n = Perlin3(seed)
    r = np.random.default_rng(seed)
    cs = r.normal(size=(count, 3))
    cs /= np.linalg.norm(cs, axis=1, keepdims=True)
    rad = np.clip(0.012 + r.pareto(1.4, count) * 0.018, 0.012, 0.32)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        h = fbm(n, x * 3, y * 3, z * 3, 9)
        m = smooth(0.52, 0.58, fbm(n, x * 1.3 + 5, y * 1.3, z * 1.3, 5))
        col = mix(np.array(base), np.array(mare), m * 0.85)
        col = col * (0.85 + 0.3 * (fbm(n, x * 18, y * 18, z * 18, 4) - 0.5))[..., None]
        height = h * 0.4 - m * 0.15
        ray_b = np.zeros(x.shape)
        for c, rr in zip(cs, rad):
            d = np.arccos(np.clip(q @ c, -1, 1)) / rr
            if not (d < 3).any():
                continue
            wob = 1 + 0.08 * n(q[..., 0] * 40 + c[0] * 9, q[..., 1] * 40, q[..., 2] * 40)
            dd = d * wob
            bowl = np.where(dd < 1, -(1 - dd ** 2) * 0.9, 0)
            rim = np.exp(-((dd - 1) / 0.22) ** 2) * 0.45
            ejecta = np.where(dd > 1, np.exp(-(dd - 1) * 2.5) * 0.12, 0)
            peak = np.where(rr > 0.08, np.exp(-(dd / 0.18) ** 2) * 0.35, 0)
            height = height + (bowl + rim + ejecta + peak) * rr * 2.2
            # Fresh ejecta is brighter; the floor of a big crater darker.
            ray_b = ray_b + np.where(dd > 1, np.exp(-(dd - 1) * 1.8) * 0.18, 0) * (rr < 0.06)
            ray_b = ray_b - np.where(dd < 0.8, 0.12, 0) * (rr > 0.08)
        col = col * (1 + np.clip(ray_b, -0.3, 0.5))[..., None]
        return col, height, None
    return f


def banded(seed, stops, bands=11, turb=1.0, storms=(), fine=1.0):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        # Swirls: warp more where the bands shear against each other.
        shear = np.cos(y * bands * np.pi * 0.5)
        wx, wy, wz = warp(n, x * 2.2, y * 6.0, z * 2.2, 0.35 * turb * (0.5 + 0.5 * np.abs(shear)), 6)
        lat = y + 0.05 * turb * (fbm(n, wx, wy, wz, 7) - 0.5) * 2
        band = 0.5 + 0.5 * np.sin(lat * bands * np.pi * 0.5 + 0.8 * (fbm(n, lat * 30, 0.3, 1.1, 4) - 0.5) * 6)
        streaks = fbm(n, x * 3 * fine, y * 90, z * 3 * fine, 4)
        t = np.clip(band * 0.75 + streaks * 0.25 + 0.15 * (fbm(n, wx * 3, wy * 3, wz * 3, 5) - 0.5), 0, 1)
        col = ramp(t, stops)
        for (lon, la, size, scol) in storms:
            c = np.array([np.cos(la) * np.sin(lon), np.sin(la), np.cos(la) * np.cos(lon)])
            d = np.arccos(np.clip(q @ c, -1, 1))
            dx = np.arctan2(q[..., 0] * c[2] - q[..., 2] * c[0], 1)
            e = d / size
            ang = np.arctan2(q[..., 1] - c[1], (q @ np.cross([0, 1.0, 0], c)) * 1.0)
            swirl = 0.5 + 0.5 * np.sin(ang * 2 + e * 9 + fbm(n, x * 20, y * 20, z * 20, 3) * 4)
            m = smooth(1.15, 0.6, e)
            col = mix(col, np.array(scol) * (0.75 + 0.35 * swirl)[..., None], m)
        height = t * 0.15
        return col, height, None
    return f


def desert_world(seed):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        wx, wy, wz = warp(n, x * 2, y * 2, z * 2, 0.5)
        h = fbm(n, wx, wy, wz, 9)
        cany = ridged(n, x * 2.5 + 2, y * 2.5, z * 2.5, 6)
        dark = smooth(0.45, 0.62, fbm(n, x * 1.5 + 7, y * 1.5, z * 1.5, 6))
        col = ramp(h, [(0, (0.30, 0.10, 0.05)), (0.45, (0.62, 0.27, 0.12)), (0.7, (0.80, 0.45, 0.24)), (1, (0.92, 0.70, 0.50))])
        col = mix(col, np.array([0.28, 0.13, 0.09]), dark * 0.55)
        col = col * (1 - 0.18 * smooth(0.6, 0.95, cany))[..., None]
        cap = smooth(0.93, 0.96, np.abs(y) + 0.05 * (fbm(n, x * 8, y * 8, z * 8, 5) - 0.5))
        col = mix(col, np.array([0.95, 0.92, 0.9]), cap)
        height = h * 0.6 - cany * 0.4
        return col, height, None
    return f


def lava_world(seed):
    n = Perlin3(seed)

    def f(q):
        x, y, z = q[..., 0], q[..., 1], q[..., 2]
        wx, wy, wz = warp(n, x * 2.5, y * 2.5, z * 2.5, 0.7)
        cracks = ridged(n, wx, wy, wz, 8)
        crust = fbm(n, x * 6, y * 6, z * 6, 7)
        col = ramp(crust, [(0, (0.03, 0.025, 0.025)), (1, (0.17, 0.13, 0.11))])
        heat = smooth(0.55, 0.85, cracks)
        pools = smooth(0.62, 0.7, fbm(n, x * 1.8 + 3, y * 1.8, z * 1.8, 6))
        heat = np.clip(heat + pools, 0, 1)
        em = ramp(heat, [(0, (0, 0, 0)), (0.3, (0.6, 0.06, 0.0)), (0.7, (1.0, 0.35, 0.03)), (1, (1.0, 0.85, 0.45))]) * 3.0 * heat[..., None]
        height = crust * 0.5 - heat * 0.4
        return col * (1 - heat)[..., None], height, em
    return f


def ring_profile(seed, gaps=((0.30, 0.012), (0.62, 0.05), (0.86, 0.012))):
    """Ring density across the ring (0 inner, 1 outer): a faint inner ring, a dense bright
    middle, a wide gap and a dimmer outer ring, all with fine ringlets."""
    n = Perlin3(seed)

    def dens(t):
        base = np.interp(t, [0, 0.12, 0.28, 0.32, 0.55, 0.62, 0.68, 0.95, 1.0],
                            [0.10, 0.18, 0.30, 0.80, 1.00, 0.85, 0.60, 0.55, 0.0])
        fine = 0.55 + 0.45 * fbm(n, t * 140, 0.37, 0.71, 4)
        lets = 0.85 + 0.15 * fbm(n, t * 600, 3.1, 1.7, 2)
        d = base * fine * lets
        for g, wdt in gaps:
            d = d * (0.08 + 0.92 * smooth(wdt * 0.4, wdt, np.abs(t - g)))
        return np.clip(d * smooth(0, 0.03, t) * smooth(1, 0.97, t), 0, 1)
    return dens


def rings_for(inner, outer, seed, c0, c1, opacity=0.9):
    prof = ring_profile(seed)

    def dens_r(r):
        t = np.clip((r - inner) / (outer - inner), 0, 1)
        return prof(t) * opacity

    def col_r(r):
        t = np.clip((r - inner) / (outer - inner), 0, 1)
        return mix(np.array(c0), np.array(c1), np.clip(prof(t) * 1.2, 0, 1))
    return inner, outer, dens_r, col_r
