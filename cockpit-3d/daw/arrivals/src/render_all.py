"""Renders the arrival pictures and the two suns, supersampled 2x, at 1024 on the long side,
into the folder above this one, and writes sun_directions.json there: for each planet, the
sun that lights it and where that sun is from the planet's centre (yaw + right, pitch + up,
in degrees), so its lit side faces it. numpy and Pillow only; about half an hour.

    python3 render_all.py [name,name,...]
"""
import json, os, sys, time
import numpy as np
import planets as P, nebulae as N, blackhole as B, sun, common

SS = int(os.environ.get("SS", "2048"))   # internal size (long side)
OUT = int(os.environ.get("OUT", "1024"))
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
S = SS
wide = (S, S * 2 // 3)


# Each planet's light, (x right, y up, z toward the viewer), and its sun.
LIGHT = {"ocean_world": (-0.75, 0.25, 0.45), "moon_grey": (-0.93, 0.25, 0.2), "ringed_giant": (-0.6, 0.3, 0.74),
         "ice_giant": (0.6, 0.35, 0.72), "red_desert": (0.8, 0.3, 0.5), "lava_world": (-0.4, 0.5, 0.2),
         "violet_giant": (0.65, 0.05, 0.76)}
STAR = {"lava_world": "sun_orange", "violet_giant": "sun_orange"}


def ocean():
    surf, sea = P.terran(12)
    return P.render(S, S, surf, light=LIGHT["ocean_world"], radius=0.8, frame=P.rot(20, 40, -15),
                    atmo=((0.35, 0.6, 1.0), 0.025, 1.0), clouds=P.cloud_layer(13),
                    night=P.city_lights(14, sea), spec=sea, bump=0.6)


JOBS = {
    "black_hole": lambda: B.render(*wide),
    "ocean_world": ocean,
    "moon_grey": lambda: P.render(S, S, P.cratered(11), light=LIGHT["moon_grey"], radius=0.82,
                                  frame=P.rot(10, 20), bump=2.5),
    "ringed_giant": lambda: P.render(S, S, P.banded(14, [(0, (0.50, 0.30, 0.17)), (0.35, (0.80, 0.60, 0.38)),
                                     (0.6, (0.93, 0.85, 0.68)), (0.8, (0.75, 0.55, 0.35)), (1, (0.60, 0.40, 0.25))],
                                     storms=[(0.4, -0.35, 0.09, (0.80, 0.42, 0.25))]),
                                     light=LIGHT["ringed_giant"], radius=0.42, frame=P.rot(22, 0, -18),
                                     rings=P.rings_for(1.25, 2.25, 15, (0.50, 0.40, 0.30), (0.92, 0.84, 0.70), 0.97),
                                     atmo=((0.9, 0.75, 0.5), 0.01, 0.3), bump=0.2),
    "ice_giant": lambda: P.render(S, S, P.banded(16, [(0, (0.30, 0.58, 0.68)), (0.5, (0.48, 0.78, 0.86)),
                                  (1, (0.70, 0.90, 0.95))], bands=6, turb=0.15, fine=0.3,
                                  storms=[(-0.5, -0.4, 0.07, (0.18, 0.35, 0.55))]), light=LIGHT["ice_giant"],
                                  radius=0.45, frame=P.rot(-25, 0, 28),
                                  rings=P.rings_for(1.45, 1.95, 17, (0.35, 0.45, 0.55), (0.70, 0.80, 0.88), 0.5),
                                  atmo=((0.55, 0.85, 1.0), 0.03, 1.0), bump=0.1),
    "red_desert": lambda: P.render(S, S, P.desert_world(18), light=LIGHT["red_desert"], radius=0.8,
                                   frame=P.rot(20, -30, 10), atmo=((1.0, 0.6, 0.4), 0.012, 0.6), bump=1.6),
    "lava_world": lambda: P.render(S, S, P.lava_world(19), light=LIGHT["lava_world"], radius=0.8, frame=P.rot(10, 70),
                                   atmo=((1.0, 0.4, 0.15), 0.02, 0.5), bump=1.0),
    "violet_giant": lambda: P.render(S, S, P.banded(20, [(0, (0.28, 0.12, 0.40)), (0.4, (0.55, 0.32, 0.72)),
                                     (0.7, (0.80, 0.66, 0.92)), (1, (0.95, 0.88, 1.0))], bands=9, turb=1.6,
                                     storms=[(-0.35, -0.25, 0.14, (0.95, 0.85, 1.0)), (0.5, 0.45, 0.05, (0.35, 0.15, 0.5))]),
                                     light=LIGHT["violet_giant"], radius=0.8, frame=P.rot(12, 30, -8),
                                     atmo=((0.75, 0.55, 1.0), 0.02, 1.0), bump=0.2),
    "emission_nebula": lambda: N.emission_nebula(*wide),
    "blue_nebula": lambda: N.blue_nebula(*wide),
    "spiral_galaxy": lambda: N.spiral_galaxy(*wide),
    "ring_nebula": lambda: N.ring_nebula(S, S),
    "sun_yellow": lambda: sun.render(S, S, temp=5600, seed=31),
    "sun_orange": lambda: sun.render(S, S, temp=4300, seed=32),
}


def directions():
    out = {}
    for name, v in LIGHT.items():
        v = np.array(v) / np.linalg.norm(v)
        out[name] = {"sun": STAR.get(name, "sun_yellow"),
                     "yaw_deg": round(float(np.degrees(np.arctan2(v[0], -v[2]))), 1),
                     "pitch_deg": round(float(np.degrees(np.arcsin(v[1]))), 1)}
    with open(os.path.join(DEST, "sun_directions.json"), "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")

if __name__ == "__main__":
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else list(JOBS)
    for name in only:
        t = time.time()
        rgb, a = JOBS[name]()
        common.save(os.path.join(DEST, f"{name}.png"), rgb, a, OUT)
        print(name, round(time.time() - t), "s", flush=True)
    directions()
