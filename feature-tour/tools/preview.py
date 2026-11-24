#!/usr/bin/env python3
"""Rough stills of the feature tour, drawn from the project file with a pinhole camera:
images, shapes and text placed as the file says, the scene camera and each keyframe's
camera applied, captions over their chapters. No effects, lights or blending: this
checks layout and framing, it is not the engine's render.

    python3 preview.py feature-tour.json out_dir
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

path, out = sys.argv[1], sys.argv[2]
root = os.path.dirname(os.path.abspath(path))
d = json.load(open(path))
SRC = {s["id"]: s for s in d["sources"]}
SCN = {s["id"]: s for s in d["scenes"]}
W, H = 960, 540  # half size
K = 0.5
FONT = {"regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"}
cache = {}


def rgba(c):
    c = c.lstrip("#")
    if len(c) == 6:
        c += "ff"
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4, 6))


def content(it):
    s = SRC[it["source_id"]]
    k, st = s["kind"].get("kind", s["kind"]["type"]), s.get("settings", {})
    g = it["geometry"]
    cr = it.get("crop") or {}
    key = (it["source_id"], round(g["size"]["width"]), round(g["size"]["height"]), tuple(sorted(cr.items())))
    if key in cache:
        return cache[key]
    im = None
    if k == "scene":
        im = render_flat(s["kind"]["scene_id"])
        if any(cr.values()):
            iw_, ih_ = im.size
            im = im.crop((cr["left"], cr["top"], iw_ - cr["right"], ih_ - cr["bottom"]))
    elif k == "image":
        im = Image.open(os.path.join(root, st["file"]["path"])).convert("RGBA")
        if any(cr.values()):
            iw_, ih_ = im.size
            im = im.crop((cr["left"], cr["top"], iw_ - cr["right"], ih_ - cr["bottom"]))
    elif k == "backdrop":
        w_, h_ = 640, 360
        a, b = np.array(rgba("#" + st["color"].lstrip("#"))[:3]), np.array(rgba("#" + st["accent"].lstrip("#"))[:3])
        yy, xx = np.mgrid[0:h_, 0:w_]
        r = np.sqrt(((xx / w_ - st["light_x"]) * 1.6) ** 2 + (yy / h_ - st["light_y"]) ** 2)
        t = np.clip(r / 0.9, 0, 1)[..., None]
        arr = (a * (1 - t) + b * t).astype(np.uint8)
        im = Image.fromarray(arr, "RGB").convert("RGBA")
    elif k == "shape":
        w_, h_ = st["width"], st["height"]
        im = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        fill = rgba(st["color"])
        if st.get("fill") == "radial":
            arr = np.zeros((h_, w_, 4), np.uint8)
            yy, xx = np.mgrid[0:h_, 0:w_]
            r = np.clip(np.sqrt(((xx - w_ / 2) / (w_ / 2)) ** 2 + ((yy - h_ / 2) / (h_ / 2)) ** 2), 0, 1)
            arr[..., :3] = fill[:3]
            arr[..., 3] = (fill[3] * (1 - r)).astype(np.uint8)
            im = Image.fromarray(arr, "RGBA")
        elif st.get("shape") == "ellipse":
            dr.ellipse([0, 0, w_ - 1, h_ - 1], fill=fill)
        else:
            bw = int(st.get("border_width", 0))
            dr.rounded_rectangle([0, 0, w_ - 1, h_ - 1], radius=int(st.get("radius", 0)), fill=fill,
                                 outline=rgba(st.get("border_color", "#ffffffff")) if bw else None, width=bw)
    elif k in ("text", "timer"):
        txt = st.get("text", "") if k == "text" else "09:59"
        size = int(st["size"])
        if st.get("font"):
            f = ImageFont.truetype(os.path.join(root, st["font"]["path"]), size)
        else:
            f = ImageFont.truetype(FONT["bold" if "bold" in st.get("face", "") else "regular"], size)
        wrap = st.get("wrap_width", 0)
        lines = []
        for para in txt.split("\n"):
            if not wrap:
                lines.append(para)
                continue
            cur = ""
            for word in para.split():
                trial = (cur + " " + word).strip()
                if f.getlength(trial) > wrap and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
        ls = st.get("letter_spacing", 0.0)
        widths = [f.getlength(l_) + ls * len(l_) for l_ in lines]
        asc, desc = f.getmetrics()
        lh = asc + desc
        w_, h_ = int(wrap or max(widths + [1])) + 1, lh * len(lines)
        im = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        for n, l_ in enumerate(lines):
            x = {"left": 0, "center": (w_ - widths[n]) / 2, "right": w_ - widths[n]}[st.get("align", "left")]
            if ls:
                for ch in l_:
                    dr.text((x, n * lh), ch, font=f, fill=rgba(st["color"]))
                    x += f.getlength(ch) + ls
            else:
                dr.text((x, n * lh), l_, font=f, fill=rgba(st["color"]))
    cache[key] = im
    return im


def fit_box(im, w, h, mode):
    """The content's quad inside the item box (local coords, centred)."""
    if mode in ("stretch", "fill"):
        return w, h
    iw, ih = im.size
    sc = min(w / iw, h / ih)
    return iw * sc, ih * sc


def coeffs(dst, src):
    m = []
    for (x, y), (u, v) in zip(dst, src):
        m.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        m.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(m, float)
    b = np.array([c for p in src for c in p], float)
    return np.linalg.solve(a, b)


def project(camera):
    if camera is None:
        return lambda p: (p[0] * K, p[1] * K, 1.0)
    P = np.array([camera["position"][a] for a in "xyz"])
    Tg = np.array([camera["target"][a] for a in "xyz"])
    f = (Tg - P) / np.linalg.norm(Tg - P)
    r = np.cross(f, [0, 1, 0])
    r /= np.linalg.norm(r)
    dn = np.cross(r, f)
    F = 540 / math.tan(math.radians(camera.get("fov_deg", 45) / 2))

    def pr(q):
        v = np.array(q) - P
        zc = v @ f
        if zc < 1:
            return None
        return ((960 + (v @ r) / zc * F) * K, (540 + (v @ dn) / zc * F) * K, zc)
    return pr


BUILT = {c["action"].get("item_id") for sc in d["scenes"] for tl in sc.get("timelines", [])
         for c in tl.get("cues", []) if c["action"]["type"] == "item.show"}


def render_flat(sid):
    global W, H, K
    keep = (W, H, K)
    W, H, K = 1920, 1080, 1.0
    try:
        im = render([sid], {}, {}, None)
    finally:
        W, H, K = keep
    return im.convert("RGBA")


def render(scene_ids, camera_of, vis_over, label, geo_over=None):
    geo_over = geo_over or {}
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0 if label is None else 255))
    for sid in scene_ids:
        sc = SCN[sid]
        cam_ = camera_of.get(sid, sc.get("camera"))
        pr = project(cam_)
        for it in sc["items"]:
            vis = vis_over.get(it["id"], it.get("visible", True) or it["id"] in BUILT)
            if it["id"] in geo_over:
                it = dict(it, geometry=geo_over[it["id"]])
            if not vis or SRC[it["source_id"]]["kind"].get("kind", "scene") not in (
                    "image", "shape", "text", "timer", "backdrop", "scene"):
                continue
            im = content(it)
            g = it["geometry"]
            cw, ch = fit_box(im, g["size"]["width"], g["size"]["height"], g.get("fit_mode", "fit"))
            turn = math.radians(g.get("turn_deg", 0.0))
            z0 = g.get("depth_px", 0.0)
            cx, cy = g["center"]["x"], g["center"]["y"]
            corners = []
            for lx, ly in ((-cw / 2, -ch / 2), (cw / 2, -ch / 2), (cw / 2, ch / 2), (-cw / 2, ch / 2)):
                corners.append(pr((cx + lx * math.cos(turn), cy + ly, z0 - lx * math.sin(turn))))
            if any(c is None for c in corners):
                continue
            dst = [(c[0], c[1]) for c in corners]
            xs, ys = [p[0] for p in dst], [p[1] for p in dst]
            if max(xs) < 0 or min(xs) > W or max(ys) < 0 or min(ys) > H or max(xs) - min(xs) < 1:
                continue
            iw, ih = im.size
            co = coeffs(dst, [(0, 0), (iw, 0), (iw, ih), (0, ih)])
            layer = im.transform((W, H), Image.PERSPECTIVE, tuple(co), Image.BILINEAR)
            if cam_ and cam_.get("focus_px") and cam_.get("blur_px"):
                zc = pr((cx, cy, z0))[2]
                r = cam_["blur_px"] * abs(zc - cam_["focus_px"]) / zc * K
                if r > 0.5:
                    from PIL import ImageFilter
                    layer = layer.filter(ImageFilter.GaussianBlur(float(r)))
            op = it.get("opacity", 1.0)
            if op < 1:
                a = layer.getchannel("A").point(lambda v: int(v * op))
                layer.putalpha(a)
            canvas.alpha_composite(layer)
    if label is None:
        return canvas
    dr = ImageDraw.Draw(canvas)
    dr.text((10, H - 20), label + "  ·  layout preview, not the engine's render", fill=(255, 255, 255, 150),
            font=ImageFont.truetype(FONT["regular"], 12))
    return canvas.convert("RGB")


os.makedirs(out, exist_ok=True)
tour = next(s for s in d["shows"] if s["show_id"] == "tour")
t, frames = 0, []
for n, clip in enumerate(tour["program"]):
    sid = clip["scene_id"]
    over = [c["scene_id"] for tr in tour["overlays"] for c in tr["clips"]
            if c["start_ms"] <= t + 2000 < c["start_ms"] + c["length_ms"]]
    stamp = f"{t // 60000}:{t // 1000 % 60:02d}"
    frames.append((f"{n:02d}a", render([sid] + over, {}, {}, f"{stamp} {SCN[sid]['name']}")))
    # every keyframe of this scene, in the order the show loads them
    kfs = [m for m in tour["keyframes"] if t <= m["at_ms"] < t + clip["length_ms"] and m.get("keyframe_id")]
    for m, mk in enumerate(kfs):
        kf = SCN[mk["keyframe_id"]]
        vis = {o["item_id"]: o["visible"] for o in kf.get("overrides", []) if "visible" in o}
        cam = {sid: kf["camera"]} if kf.get("camera") else {}
        geo = {o["item_id"]: o["geometry"] for o in kf.get("overrides", []) if "geometry" in o}
        frames.append((f"{n:02d}{chr(98 + m)}", render([sid], cam, vis, f"{stamp} {SCN[sid]['name']} · {kf['name']}", geo)))
    t += clip["length_ms"]
for name, im in frames:
    im.save(os.path.join(out, name + ".jpg"), quality=85)
cols = 4
rows = (len(frames) + cols - 1) // cols
sheet = Image.new("RGB", (cols * 480, rows * 270), (20, 20, 20))
for i, (name, im) in enumerate(frames):
    sheet.paste(im.resize((480, 270)), ((i % cols) * 480, (i // cols) * 270))
sheet.save(os.path.join(out, "contact-sheet.jpg"), quality=85)
print(len(frames), "frames")
