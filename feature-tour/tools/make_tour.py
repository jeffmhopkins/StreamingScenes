#!/usr/bin/env python3
"""Writes the JStream feature-tour demo project (collection schema 22, ADR-0210 shows).

    python3 make_tour.py OUT_DIR/feature-tour.json

Real screenshots of the app (OUT_DIR/media/*.jpg) sit as cards in 3D scenes; keyframe
scenes move the scene camera onto one part of a screenshot at a time, with a highlight
box and a callout that appear with it. The show steps through those keyframes, with a
chapter caption overlay over each chapter. The written file is loose; saving it once in
JStream puts it in the canonical form the engine writes.
"""
import json
import math
import os
import sys

from PIL import Image

W, H = 1920, 1080
TAN = math.tan(math.radians(22.5))
OUT = sys.argv[1] if len(sys.argv) > 1 else "feature-tour.json"
MEDIA = os.path.join(os.path.dirname(os.path.abspath(OUT)), "media")

# Design tokens: the app's own (crates/jstream-ui/style.css), per design-language.md.
T = {
    "text": "#e6e8ebff", "text_soft": "#c9ced6ff", "muted": "#9aa1acff", "dim": "#7d8590ff",
    "faint": "#5a606bff", "accent": "#4c8dff", "accent_a": "#4c8dffff", "link": "#8ab4ffff",
    "panel": "#16191eff", "panel86": "#16191edb", "raised": "#1a1d23ff", "menu": "#1f232aff",
    "border": "#2e333bff", "line": "#262a31ff", "edge": "#ffffff12", "ok": "#3fb27fff",
    "dimmer": "#0506089e", "code_num": "#f2a07bff", "code_call": "#82aaffff", "teal": "#7fd1c7ff",
    "purple": "#b07cffff", "radius": 14.0,
}
TXT, TXT2, MUTED, ACCENT, ACCENT_A, PANEL = (T["text"], T["muted"], T["dim"], T["accent"],
                                              T["accent_a"], T["menu"])
LINK = T["link"]
# IBM Plex, the app's own type (ADR-0077), as font files next to the project.
FONTS = {"regular": "IBMPlexSans-Regular-Latin1.ttf", "bold": "IBMPlexSans-SemiBold-Latin1.ttf",
         "mono": "IBMPlexMono-Regular-Latin1.ttf", "mono_bold": "IBMPlexMono-SemiBold-Latin1.ttf"}
# The curves of design-language.md §7, as JStream easings.
def bez(x1, y1, x2, y2):
    return {"cubic_bezier": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}}
E_ENTER, E_GLIDE, E_STD, E_EXIT, E_ORBIT = (bez(0.05, 0.7, 0.1, 1.0), bez(0.16, 1.0, 0.3, 1.0),
                                            bez(0.2, 0.0, 0.0, 1.0), bez(0.3, 0.0, 0.8, 0.15),
                                            bez(0.45, 0.0, 0.15, 1.0))

sources, scenes, src_ids = [], [], set()
TEXT_SCALE = {}  # item ID -> how much its text is scaled (callouts on a zoomed-in plane)


def source(sid, name, kind, settings, **extra):
    assert sid not in src_ids, sid
    src_ids.add(sid)
    s = {"id": sid, "name": name, "kind": {"type": "builtin", "kind": kind}, "kind_version": 1,
         "settings": settings}
    s.update(extra)
    sources.append(s)
    return sid


def text_src(sid, name, text, size, color=None, face="regular", align="left", **kw):
    bundled = "bold" if face in ("bold", "mono_bold") else "regular"
    st = {"text": text, "size": float(size), "color": color or TXT, "face": bundled, "align": align,
          "font": {"type": "asset", "root": "collection", "path": f"fonts/{FONTS[face]}"}}
    st.update(kw)
    return source(sid, name, "text", st)


def shape_src(sid, name, w, h, color, shape="rectangle", radius=0.0, **kw):
    st = {"shape": shape, "width": max(1, int(round(w))), "height": max(1, int(round(h))),
          "radius": float(radius), "color": color}
    st.update(kw)
    return source(sid, name, "shape", st)


def image_src(sid, name, file):
    return source(sid, name, "image", {"file": {"type": "asset", "root": "collection",
                                                "path": f"media/{file}"}})


def geom(cx, cy, w, h, fit="fit", **kw):
    g = {"center": {"x": float(cx), "y": float(cy)}, "size": {"width": float(w), "height": float(h)},
         "fit_mode": fit}
    for k, v in kw.items():
        g[k] = float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
    return g


def item(iid, sid, g, visible=True, opacity=None, effects=None, motion=None, blend=None):
    it = {"id": iid, "source_id": sid, "geometry": g,
          "crop": {"left": 0, "top": 0, "right": 0, "bottom": 0}, "visible": visible}
    if opacity is not None:
        it["opacity"] = opacity
    if blend:
        it["blend"] = blend
    if effects:
        it["effects"] = effects
    if motion:
        it["motion"] = motion
    return it


def fx(fid, kind, **settings):
    return {"id": fid, "kind": kind, "kind_version": 1, "settings": settings}


def mod(mid, prop, kind, clock="engine", **kw):
    m = {"modifier_id": mid, "property": prop, "kind": kind, "clock": clock}
    m.update(kw)
    return m


def scene(sid, name, items, **kw):
    s = {"id": sid, "name": name}
    s.update(kw)
    s["items"] = items
    scenes.append(s)
    return s


def act(t, **kw):
    a = {"type": t}
    a.update(kw)
    return a


def cam(px, py, pz, tx, ty, tz=0.0, fov=45.0, roll=0.0, **kw):
    c = {"position": {"x": float(px), "y": float(py), "z": float(pz)},
         "target": {"x": float(tx), "y": float(ty), "z": float(tz)}, "fov_deg": float(fov),
         "roll_deg": float(roll)}
    c.update(kw)
    return c


def dist(vw):
    """Camera distance at which the visible width is `vw` plane pixels (16:9, fov 45)."""
    return vw * (9 / 16) / (2 * TAN)


LABEL = ["tour"]


def shadow():
    """The window shadow: one light, from above."""
    return fx("shadow", "drop_shadow", color="#000000b3", offset_x=0.0, offset_y=40.0, blur=100.0)


def popout_shadow():
    return fx("shadow", "drop_shadow", color="#00000099", offset_x=0.0, offset_y=18.0, blur=48.0)


def card_effects(radius=None):
    """A frameless window: rounded corners, a hairline edge, the window shadow."""
    return [fx("round", "rounded_corners", radius=radius or T["radius"], border_width=1.0,
               border_color=T["edge"]), shadow()]


# ---------------------------------------------------------------- shared look
source("bd", "Tour backdrop", "backdrop", {"style": "canvas", "color": "#0d0f13", "accent": "#08090b",
       "texture": 0.04, "scale": 1.5, "light": 0.2, "light_x": 0.72, "light_y": 0.38,
       "vignette": 0.55, "grain": 0.05, "seed": 12, "width": W, "height": H})
shape_src("soft_light", "Tour light pool", 1200, 700, ACCENT + "1a", shape="ellipse", fill="radial",
          color2=ACCENT + "00")


def backdrop_items(prefix, cam3d=False, depth=-2400.0, span=3.2):
    """In a 3D scene the backdrop is a big card far behind everything, so camera moves
    never show its edge."""
    if cam3d:
        return [item(f"{prefix}_i_bd", "bd", geom(W / 2, H / 2, W * span, H * span, fit="fill",
                                                   depth_px=depth))]
    return [item(f"{prefix}_i_bd", "bd", geom(W / 2, H / 2, W, H, fit="fill"))]


def est_lines(text, size, wrap):
    lines, cur = 1, 0.0
    for w_ in text.split():
        wl = (len(w_) + 1) * size * 0.53
        if cur + wl > wrap and cur > 0:
            lines, cur = lines + 1, wl
        else:
            cur += wl
    return lines


# ---------------------------------------------------------------- screenshot chapters
def screenshot_chapter(sid, name, shots, focuses, base_cam=None):
    """`shots`: [(key, file, cx, cy, card_w)], cards on the z=0 plane. `focuses`:
    [(keyframe name, shot key, (x0, y0, x1, y1) as fractions of the shot, title, body,
    side of the callout)]. Returns the keyframe scene IDs in order."""
    items = backdrop_items(sid, cam3d=True)
    planes, shots_by_key = {}, {}
    for key, file, cx, cy, cw in shots:
        shots_by_key[key] = file.split('.')[0].replace('-', '_')
        iw, ih = Image.open(os.path.join(MEDIA, file)).size
        ch = cw * ih / iw
        planes[key] = (cx, cy, cw, ch, iw)
        src = f"img_{file.split('.')[0].replace('-', '_')}"
        if src not in src_ids:
            image_src(src, f"Screenshot: {file}", file)
        items.append(item(f"{sid}_i_{key}", src, geom(cx, cy, cw, ch, fit="stretch"),
                          effects=card_effects()))
    kfs, focus_items = [], []
    for n, (fkey, shot, (x0, y0, x1, y1), title, body, side) in enumerate(focuses):
        cx, cy, cw, ch, iw = planes[shot]
        ih = iw * ch / cw
        rx0, ry0 = cx - cw / 2 + x0 * cw, cy - ch / 2 + y0 * ch
        rx1, ry1 = cx - cw / 2 + x1 * cw, cy - ch / 2 + y1 * ch
        rw, rh = rx1 - rx0, ry1 - ry0
        # push in so the target fills about 55 to 65% of the frame, never past 2.2x of the window
        vw = max(1920 * cw / (iw * 1.7), rw / 0.6, rh * 16 / 9 / 0.62, 560)
        s = vw / 1920
        padx, pady = 24 * s, 18 * s
        pw = 520 * s
        wrap = 520 - 48
        lines = est_lines(body, 22, wrap)
        ph = (30 * 1.2 + 8 + lines * 22 * 1.4) * s + 2 * pady
        gap = 28 * s
        if side == "right":
            px, py = rx1 + gap + pw / 2, max(ry0 + ph / 2, (ry0 + ry1) / 2)
            box = (rx0, min(ry0, py - ph / 2), px + pw / 2, max(ry1, py + ph / 2))
        elif side == "left":
            px, py = rx0 - gap - pw / 2, max(ry0 + ph / 2, (ry0 + ry1) / 2)
            box = (px - pw / 2, min(ry0, py - ph / 2), rx1, max(ry1, py + ph / 2))
        elif side == "above":
            px, py = rx0 + pw / 2, ry0 - gap - ph / 2
            box = (min(rx0, px - pw / 2), py - ph / 2, max(rx1, px + pw / 2), ry1)
        else:
            px, py = rx0 + pw / 2, ry1 + gap + ph / 2
            box = (min(rx0, px - pw / 2), ry0, max(rx1, px + pw / 2), py + ph / 2)
        vw = max(vw, (box[2] - box[0]) * 1.16, (box[3] - box[1]) * 16 / 9 * 1.16)
        tx, ty = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        d = dist(vw)
        cid = f"{sid}_c{n}"
        # spotlight: dim everything, then the target again on top of the dim, ringed
        dim = shape_src(f"{cid}_dim", f"Spotlight dim: {title}", 64, 36, T["dimmer"])
        focus_items.append(item(f"{cid}_i_dim", dim, geom((rx0 + rx1) / 2, (ry0 + ry1) / 2, vw * 3, vw * 3 * 9 / 16,
                                                          fit="stretch", depth_px=1), visible=False))
        crop = {"left": int(x0 * iw), "top": int(y0 * ih), "right": int((1 - x1) * iw),
                "bottom": int((1 - y1) * ih)}
        lit = item(f"{cid}_i_lit", f"img_{shots_by_key[shot]}", geom((rx0 + rx1) / 2, (ry0 + ry1) / 2, rw, rh,
                                                                     fit="stretch", depth_px=2), visible=False,
                   effects=[fx("round", "rounded_corners", radius=12.0, border_width=0.0,
                               border_color="#00000000")])
        lit["crop"] = crop
        focus_items.append(lit)
        ring_pad = 8 * s
        hb = shape_src(f"{cid}_box", f"Spotlight ring: {title}", rw / s + 16, rh / s + 16, "#00000000",
                       radius=12.0, border_width=2.0, border_color=ACCENT_A)
        focus_items.append(item(f"{cid}_i_box", hb, geom((rx0 + rx1) / 2, (ry0 + ry1) / 2, rw + 2 * ring_pad,
                                                         rh + 2 * ring_pad, fit="stretch", depth_px=3),
                                visible=False,
                                effects=[fx("glow", "glow", color=ACCENT + "59", radius=28.0, strength=0.5)]))
        # the callout chip: the app's own menu surface
        panel = shape_src(f"{cid}_panel", f"Callout chip: {title}", pw / s, ph / s, PANEL,
                          radius=10.0, border_width=1.0, border_color=T["border"])
        tsrc = text_src(f"{cid}_t", f"Callout: {title}", title, 30, face="bold")
        bsrc = text_src(f"{cid}_b", f"Callout: {title} (text)", body, 22, color=TXT2, wrap_width=int(wrap))
        z = 70
        focus_items.append(item(f"{cid}_i_panel", panel, geom(px, py, pw, ph, fit="stretch", depth_px=z),
                                visible=False,
                                effects=[fx("shadow", "drop_shadow", color="#00000080", offset_x=0.0,
                                            offset_y=12.0, blur=32.0)]))
        tw = min(pw - 2 * padx, len(title) * 30 * 0.56 * s)
        ty_ = py - ph / 2 + pady + 30 * 0.6 * s
        focus_items.append(item(f"{cid}_i_t", tsrc, geom(px - pw / 2 + padx + tw / 2, ty_, tw, 30 * 1.2 * s,
                                                         depth_px=z + 1), visible=False))
        TEXT_SCALE[f"{cid}_i_t"] = TEXT_SCALE[f"{cid}_i_b"] = s
        bh = lines * 22 * 1.4 * s
        by = ty_ + 30 * 0.6 * s + 8 * s + bh / 2
        focus_items.append(item(f"{cid}_i_b", bsrc, geom(px, by, pw - 2 * padx, bh, depth_px=z + 1),
                                visible=False))
        kfs.append((f"{sid}_k{n}", fkey, [f"{cid}_i_{k}" for k in ("dim", "lit", "box", "panel", "t", "b")],
                    cam(tx, ty, d, tx, ty)))
    items += focus_items
    if base_cam is None:
        xs = [p[0] - p[2] / 2 for p in planes.values()] + [p[0] + p[2] / 2 for p in planes.values()]
        ys = [p[1] - p[3] / 2 for p in planes.values()] + [p[1] + p[3] / 2 for p in planes.values()]
        vw = max(max(xs) - min(xs), (max(ys) - min(ys)) * 16 / 9) * 1.3
        tx, ty = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        d = dist(vw)
        base_cam = cam(tx + 0.10 * d, ty - 0.04 * d, d, tx, ty)
    scene(sid, name, items, labels=LABEL, folder="f_tour", camera=base_cam)
    for kf, fkey, show_ids, c in kfs:
        scene(kf, fkey, [], variant_of=sid, camera=c,
              overrides=[{"item_id": i, "visible": True} for i in sorted(show_ids)])
    return [k[0] for k in kfs]


# ---------------------------------------------------------------- type helpers
def text_w(text, size, face="regular", spacing=0.0):
    """A rough width for a line of Plex, to size an item's box."""
    k = {"regular": 0.53, "bold": 0.56, "mono": 0.6, "mono_bold": 0.6}[face]
    caps = sum(1 for c in text if c.isupper()) / max(1, len(text))
    return len(text) * size * (k + 0.1 * caps) + spacing * len(text) + 8


def eyebrow(prefix, number, label, x, y, size=22, depth=None):
    """The eyebrow: a chapter number in Plex Mono, then the label, upper case and tracked."""
    kw = {} if depth is None else {"depth_px": depth}
    out = []
    if number is not None:
        num = f"{number:02d}"
        text_src(f"{prefix}_num", f"{prefix}: number", num, size, color=T["dim"], face="mono")
        nw = text_w(num, size, "mono")
        out.append(item(f"{prefix}_i_num", f"{prefix}_num", geom(x + nw / 2, y, nw, size * 1.4, **kw)))
        x += nw + size * 0.6
    sp = round(size * 0.14, 1)
    text_src(f"{prefix}_eb", f"{prefix}: eyebrow", label.upper(), size, color=LINK, face="bold",
             letter_spacing=sp)
    ew_ = text_w(label.upper(), size, "bold", sp)
    out.append(item(f"{prefix}_i_eb", f"{prefix}_eb", geom(x + ew_ / 2, y, ew_, size * 1.4, **kw)))
    return out


# ---------------------------------------------------------------- chapter lower thirds (overlays)
captions = {}


def caption(key, number, kicker, title):
    """A chapter's lower third: a panel plate at the bottom-left margin, a 4 px accent bar,
    an 18 px eyebrow and a 40 px title."""
    sid = f"cap_{key}"
    tw = text_w(title, 40, "bold")
    pw = min(760, max(tw, text_w(kicker.upper(), 18, "bold", 2.5) + 40) + 58)
    ph = 20 + 18 * 1.3 + 8 + 40 * 1.15 + 22
    x0, y1 = 96, 984
    y0 = y1 - ph
    shape_src(f"{sid}_plate", f"Lower third {number}: plate", pw, ph, T["panel86"], radius=10.0,
              border_width=1.0, border_color=T["border"])
    shape_src(f"{sid}_bar", f"Lower third {number}: bar", 4, ph - 2, ACCENT_A)
    text_src(f"{sid}_t", f"Lower third {number}: title", title, 40, face="bold")
    items = [item(f"{sid}_i_plate", f"{sid}_plate", geom(x0 + pw / 2, y0 + ph / 2, pw, ph, fit="stretch"),
                  effects=[popout_shadow()]),
             item(f"{sid}_i_bar", f"{sid}_bar", geom(x0 + 3, y0 + ph / 2, 4, ph - 2, fit="stretch"))]
    items += eyebrow(sid, number, kicker, x0 + 26, y0 + 20 + 12, size=18)
    items.append(item(f"{sid}_i_t", f"{sid}_t", geom(x0 + 26 + tw / 2, y0 + 20 + 18 * 1.3 + 8 + 23, tw, 46)))
    scene(sid, f"Lower third · {title}", items, folder="f_overlays")
    captions[key] = sid


# ---------------------------------------------------------------- 0 Holding
text_src("hold_title", "Holding: title", "We start in a moment", 76, face="bold", align="center")
text_src("hold_sub", "Holding: subtitle", "A short tour of JStream, a live streaming studio", 32,
         color=TXT2, align="center")
source("hold_timer", "Holding: countdown", "timer", {"mode": "countdown", "duration": 600,
       "format": "mm:ss", "end_text": "Starting", "size": 56.0, "face": "regular",
       "font": {"type": "asset", "root": "collection", "path": f"fonts/{FONTS['mono']}"},
       "color": T["text_soft"], "align": "center", "letter_spacing": 2.0})
shape_src("hold_rule", "Holding: rule", 120, 2, T["border"])
hold_eb = eyebrow("hold", None, "JStream feature tour", 0, 360)
for it_ in hold_eb:  # centre the eyebrow
    it_["geometry"]["center"]["x"] = W / 2
scene("s_hold", "Tour 0 · Holding", backdrop_items("hold") + [
    item("hold_i_light", "soft_light", geom(1382, 410, 1200, 700, fit="stretch"), blend="additive",
         motion=[mod("roam", "x", "oscillate", amplitude=40.0, period_ms=20000)]),
] + hold_eb + [
    item("hold_i_title", "hold_title", geom(W / 2, 452, 1200, 96)),
    item("hold_i_sub", "hold_sub", geom(W / 2, 540, 1100, 48)),
    item("hold_i_rule", "hold_rule", geom(W / 2, 616, 120, 2, fit="stretch")),
    item("hold_i_timer", "hold_timer", geom(W / 2, 690, 300, 76)),
], labels=LABEL, folder="f_tour")

# ---------------------------------------------------------------- 1 Title
text_src("ttl_brand", "Title: wordmark", "JStream", 120, face="bold", letter_spacing=-3.0)
text_src("ttl_line", "Title: line",
         "A live streaming and compositing studio,\nwritten from scratch in Rust.", 32, color=TXT2)
image_src("img_editor", "Screenshot: editor.jpg", "editor.jpg")
ew, eh = Image.open(os.path.join(MEDIA, "editor.jpg")).size
ttl_eb = eyebrow("ttl", None, "A feature tour", 96, 392, depth=0)
for it_ in ttl_eb:
    it_["visible"] = False
scene("s_title", "Tour 1 · Title", backdrop_items("ttl", cam3d=True) + [
    # the hero tilt: turned -16°, tilted 6°, receding to the right
    item("ttl_i_shot", "img_editor", geom(1420, 560, 1500, 1500 * eh / ew, fit="stretch", turn_deg=-16,
                                          tilt_deg=6, depth_px=-260), effects=card_effects()),
    item("ttl_i_brand", "ttl_brand", geom(96 + 230, 480, 460, 140), visible=False),
    item("ttl_i_line", "ttl_line", geom(96 + 330, 600, 660, 96), visible=False),
] + ttl_eb, labels=LABEL, folder="f_tour",
      camera=cam(W / 2, H / 2, dist(1920), W / 2, H / 2),
      timelines=[{"timeline_id": "title_build", "name": "Title build", "duration_ms": 4000, "loop": "once",
                  "cues": [{"at_ms": 0, "action": act("item.hide", item_id=i)} for i in
                           ("ttl_i_eb", "ttl_i_brand", "ttl_i_line")] +
                          [{"at_ms": 500, "action": act("item.show", item_id="ttl_i_eb")},
                           {"at_ms": 600, "action": act("item.show", item_id="ttl_i_brand")},
                           {"at_ms": 1800, "action": act("item.show", item_id="ttl_i_line")}]}])
scene("s_title_push", "Push", [], variant_of="s_title",
      camera=cam(W / 2 + 30, H / 2 - 6, dist(1920) * 0.96, W / 2 + 30, H / 2))

# ---------------------------------------------------------------- 2 The studio
K_STUDIO = screenshot_chapter("s_studio", "Tour 2 · The studio", [("ed", "editor.jpg", 960, 540, 1600)], [
    ("Scenes", "ed", (0.005, 0.08, 0.23, 0.36), "Scenes and sources",
     "A scene stacks sources: cameras, screen and window capture, media, browser pages, text, timers and audio visualisers.", "right"),
    ("Canvas", "ed", (0.265, 0.205, 0.705, 0.615), "Composited on the GPU",
     "Each item can be cropped, turned in 3D, blended and given effects, live.", "right"),
    ("Inspector", "ed", (0.74, 0.08, 0.995, 0.70), "Edits undo per client",
     "Your undo never takes back a change made by another client: a browser, the command line or an agent.", "left"),
    ("Outputs", "ed", (0.50, 0.77, 0.995, 0.99), "Outputs apart from scenes",
     "Outputs take video mixes and audio buses, so a stream and a recording can carry different pictures and sound.", "above"),
])

# ---------------------------------------------------------------- footage (Tears of Steel, CC BY 3.0)
# Three stills from Tears of Steel, (CC) Blender Foundation, mango.blender.org, CC BY 3.0,
# each 1920 x 800. Each feed shows a 16:9 window of its still, cut with the item's crop.
TOS_W, TOS_H = 1920, 800
FEEDS = {  # key: (file, left edge of the 16:9 window, name)
    "robot": ("tos-robot.jpg", 210, "Main feed"),
    "lab": ("tos-lab.jpg", 210, "Lab cam"),
    "sky": ("tos-hovercraft.jpg", 100, "Sky cam"),
}
FEED_CW = round(TOS_H * 16 / 9)
for key, (file, _, fname) in FEEDS.items():
    assert Image.open(os.path.join(MEDIA, file)).size == (TOS_W, TOS_H)
    image_src(f"img_{key}", f"Footage: {fname} (Tears of Steel)", file)


def feed_crop(key):
    left = FEEDS[key][1]
    return {"left": left, "top": 0, "right": TOS_W - left - FEED_CW, "bottom": 0}


# The feed's lower third, a scene of its own so other scenes can show it as one layer.
LT_X, LT_Y, LT_W, LT_H = 64, 840, 800, 120
shape_src("flt_plate", "Feed lower third: plate", LT_W, LT_H, T["panel86"], radius=10.0, border_width=1.0,
          border_color=T["border"])
shape_src("flt_bar", "Feed lower third: bar", 4, LT_H - 32, ACCENT_A, radius=2.0)
text_src("flt_kick", "Feed lower third: kicker", "LIVE  ·  SECTOR 4", 22, color=LINK, face="mono_bold",
         letter_spacing=2.0)
text_src("flt_title", "Feed lower third: title", "Hover-carrier over the old city", 40, face="bold")
scene("s_feed_lt", "Tour · Feed lower third", [
    item("flt_i_plate", "flt_plate", geom(LT_X + LT_W / 2, LT_Y + LT_H / 2, LT_W, LT_H, fit="stretch")),
    item("flt_i_bar", "flt_bar", geom(LT_X + 24, LT_Y + LT_H / 2, 4, LT_H - 32, fit="stretch")),
    item("flt_i_kick", "flt_kick", geom(LT_X + 48 + 130, LT_Y + 36, 260, 30)),
    item("flt_i_title", "flt_title", geom(LT_X + 48 + 300, LT_Y + 80, 600, 54)),
], labels=LABEL, folder="f_overlays")
source("src_feed_lt", "Scene: feed lower third", None, {}, )
sources[-1]["kind"] = {"type": "scene", "scene_id": "s_feed_lt"}
sources[-1].pop("kind_version", None)
LT_CROP = {"left": LT_X, "top": LT_Y, "right": W - LT_X - LT_W, "bottom": H - LT_Y - LT_H}

# ---------------------------------------------------------------- 3 What you make (live: the Mission feed scene)
# A flat broadcast scene made only of built-in sources: the main feed and two camera feeds
# (image sources cut to 16:9 with crops), a header with a live clock (a timer), the feed's
# lower third (a nested scene) and a line saying what it is made of.
MF = {  # key: (left, top, width)
    "robot": (64, 160, 1200),
    "lab": (1296, 160, 560),
    "sky": (1296, 507, 560),
}
text_src("mf_head", "What you make: header", "MISSION FEED", 24, color=LINK, face="mono_bold", letter_spacing=3.0)
shape_src("mf_live", "What you make: live pill", 92, 34, "#d23c3cff", radius=17.0)
text_src("mf_live_t", "What you make: live", "LIVE", 18, face="mono_bold", letter_spacing=2.0, align="center")
source("mf_clock", "What you make: clock", "timer", {"mode": "clock", "clock_format": "24h", "size": 26.0,
       "face": "regular", "font": {"type": "asset", "root": "collection", "path": f"fonts/{FONTS['mono']}"},
       "color": T["text_soft"], "align": "right", "letter_spacing": 1.0})
text_src("mf_made", "What you make: made of", "Image, text, shape, timer and scene sources. No browser source.",
         22, color=TXT2, wrap_width=560)
mf_items = backdrop_items("mf") + [
    item("mf_i_head", "mf_head", geom(64 + 120, 72, 240, 34)),
    item("mf_i_live", "mf_live", geom(64 + 260 + 46, 72, 92, 34, fit="stretch")),
    item("mf_i_live_t", "mf_live_t", geom(64 + 260 + 46, 72, 92, 26)),
    item("mf_i_clock", "mf_clock", geom(1856 - 90, 72, 180, 36)),
]
for key, (x, y, w) in MF.items():
    h = w * 9 / 16
    it = item(f"mf_i_{key}", f"img_{key}", geom(x + w / 2, y + h / 2, w, h, fit="stretch"),
              effects=[fx("round", "rounded_corners", radius=10.0, border_width=1.0, border_color=T["border"])])
    it["crop"] = feed_crop(key)
    mf_items.append(it)
    text_src(f"mf_tag_{key}", f"What you make: {FEEDS[key][2]} label",
             f"CAM {list(MF).index(key) + 1}  ·  {FEEDS[key][2].upper()}", 18, color=T["text_soft"],
             face="mono_bold", letter_spacing=2.0)
    tag_w = text_w(f"CAM 1  ·  {FEEDS[key][2].upper()}", 18, "mono_bold", 2.0) + 24
    shape_src(f"mf_tagbg_{key}", f"What you make: {FEEDS[key][2]} label plate", tag_w, 34, T["dimmer"], radius=6.0)
    mf_items += [
        item(f"mf_i_tagbg_{key}", f"mf_tagbg_{key}", geom(x + 16 + tag_w / 2, y + 16 + 17, tag_w, 34, fit="stretch")),
        item(f"mf_i_tag_{key}", f"mf_tag_{key}", geom(x + 28 + 100, y + 16 + 17, 200, 26)),
    ]
lt = item("mf_i_lt", "src_feed_lt", geom(64 + 32 + LT_W / 2, 160 + 1200 * 9 / 16 - 32 - LT_H / 2, LT_W, LT_H,
                                        fit="stretch"))
lt["crop"] = dict(LT_CROP)
mf_items += [lt, item("mf_i_made", "mf_made", geom(1296 + 280, 880, 560, 70))]
scene("s_make", "Tour 3 · What you make", mf_items, labels=LABEL, folder="f_tour")

# ---------------------------------------------------------------- Keyframes (live: this chapter is the feature)
# One scene, "Mission feed", in a program frame on the right: the main feed, two camera feeds
# and the feed's lower third (a nested scene). On the left, the scene and its three keyframes as the
# Scenes list shows them. Each keyframe moves the same four items, and the show loads them in
# turn with a Move; the row of the one on screen lights up.
PARTS = {  # name: (source, crop as left, top, right, bottom edges in the source's pixels)
    "slide": ("img_robot", FEEDS["robot"][1], 0, FEEDS["robot"][1] + FEED_CW, TOS_H),
    "host": ("img_lab", FEEDS["lab"][1], 0, FEEDS["lab"][1] + FEED_CW, TOS_H),
    "guest": ("img_sky", FEEDS["sky"][1], 0, FEEDS["sky"][1] + FEED_CW, TOS_H),
    "lower": ("src_feed_lt", LT_X, LT_Y, LT_X + LT_W, LT_Y + LT_H),
}
PART_SIZE = {"img_robot": (TOS_W, TOS_H), "img_lab": (TOS_W, TOS_H), "img_sky": (TOS_W, TOS_H),
             "src_feed_lt": (W, H)}
PF_X, PF_Y, PF_W = 700, 200, 1124  # the program frame
PF_H = PF_W * 9 / 16
PK = PF_W / 1920


def part_geom(name, cx, cy, w):
    _, l_, t_, r_, b_ = PARTS[name]
    return geom(PF_X + cx * PK, PF_Y + cy * PK, w * PK, w * PK * (b_ - t_) / (r_ - l_), fit="stretch")


def part_item(name, cx, cy, w, effects=True):
    src, l_, t_, r_, b_ = PARTS[name]
    sw, sh = PART_SIZE[src]
    it = item(f"kf_i_{name}", src, part_geom(name, cx, cy, w),
              effects=[fx("round", "rounded_corners", radius=10.0, border_width=0.0, border_color="#00000000")]
              if effects else None)
    it["crop"] = {"left": l_, "top": t_, "right": sw - r_, "bottom": sh - b_}
    return it


shape_src("kf_frame", "Keyframes: program frame", PF_W + 2, PF_H + 2, "#0f1a20ff", radius=12.0,
          border_width=1.0, border_color=T["border"])
text_src("kf_frame_l", "Keyframes: program label", "PROGRAM  ·  scene Mission feed", 18, color=T["dim"], face="mono")
text_src("kf_h", "Keyframes: headline", "Keyframes are layouts", 56, face="bold")
text_src("kf_b", "Keyframes: body", "One scene, several arrangements of its items. Loading one moves everything there.",
         28, color=TXT2, wrap_width=540)
ROWS = [("Mission feed", "the scene"), ("Two-up", "keyframe"), ("Close-up", "keyframe"), ("Main feed", "keyframe")]
ROW_Y0, ROW_H = 520, 56
kf_items = backdrop_items("kf") + [
    item("kf_i_frame", "kf_frame", geom(PF_X + PF_W / 2, PF_Y + PF_H / 2, PF_W + 2, PF_H + 2, fit="stretch"),
         effects=[shadow()]),
    item("kf_i_frame_l", "kf_frame_l", geom(PF_X + 200, PF_Y + PF_H + 30, 400, 24)),
    part_item("slide", 650, 500, 1150),
    part_item("host", 1550, 330, 600),
    part_item("guest", 1550, 700, 600),
    part_item("lower", 470, 940, 760, effects=False),
] + eyebrow("kf", 3, "Keyframes", 96, 220) + [
    item("kf_i_h", "kf_h", geom(96 + 300, 300, 600, 96)),
    item("kf_i_bb", "kf_b", geom(96 + 270, 410, 540, 80)),
]
shape_src("kf_row_hl", "Keyframes: selected row", 560, ROW_H - 8, "#22324aff",
          radius=8.0)
shape_src("kf_diamond", "Keyframes: diamond", 10, 10, T["purple"], radius=1.0)
shape_src("kf_scene_ico", "Keyframes: scene mark", 12, 12, "#00000000", radius=2.0, border_width=2.0,
          border_color=T["muted"])
for n, (name, kind) in enumerate(ROWS):
    y = ROW_Y0 + n * ROW_H
    text_src(f"kf_row{n}", f"Keyframes: row {name}", name, 26, color=TXT if n == 0 else T["text_soft"],
             face="bold" if n == 0 else "regular")
    text_src(f"kf_row{n}k", f"Keyframes: row {name} kind", kind, 20, color=T["dim"])
    x_text = 96 + 20 + (0 if n == 0 else 28)
    kf_items += [
        item(f"kf_i_hl{n}", "kf_row_hl", geom(96 + 280, y, 560, ROW_H - 8, fit="stretch"), visible=(n == 0)),
        item(f"kf_i_ico{n}", "kf_scene_ico" if n == 0 else "kf_diamond",
             geom(x_text - 18 if n else 96 + 20, y, 12 if n == 0 else 10, 12 if n == 0 else 10, fit="stretch",
                  rotation_deg=0 if n == 0 else 45)),
        item(f"kf_i_row{n}", f"kf_row{n}", geom(x_text + 20 + 100, y, 200, 34)),
        item(f"kf_i_row{n}k", f"kf_row{n}k", geom(96 + 540 - 60, y, 120, 26)),
    ]
    if n == 0:
        kf_items[-2]["geometry"]["center"]["x"] = 96 + 44 + 100
kf_chips = [
    ("Two-up", "A keyframe overrides each item's place, size, crop, opacity, visibility and effects. Here the main feed steps aside."),
    ("Close-up", "A Move glides every item at once on one easing curve; each item can have its own delay and duration."),
    ("Main feed", "The show's keyframe track loads these. A sequence cue, a hotkey or a MIDI pad can too."),
]
CHIP_W = 560
for n, (t_, b_) in enumerate(kf_chips):
    lines = est_lines(b_, 22, CHIP_W - 48)
    ph = 18 + 30 * 1.2 + 8 + lines * 22 * 1.4 + 18
    y0 = 984 - ph
    shape_src(f"kf_c{n}", f"Keyframes: chip {n + 1}", CHIP_W, ph, PANEL, radius=10.0, border_width=1.0,
              border_color=T["border"])
    text_src(f"kf_c{n}t", f"Keyframes: chip {n + 1} title", t_, 30, face="bold")
    text_src(f"kf_c{n}b", f"Keyframes: chip {n + 1} text", b_, 22, color=TXT2, wrap_width=CHIP_W - 48)
    kf_items += [
        item(f"kf_i_c{n}", f"kf_c{n}", geom(96 + CHIP_W / 2, y0 + ph / 2, CHIP_W, ph, fit="stretch"), visible=False,
             effects=[fx("shadow", "drop_shadow", color="#00000080", offset_x=0.0, offset_y=12.0, blur=32.0)]),
        item(f"kf_i_c{n}t", f"kf_c{n}t", geom(96 + 24 + 100, y0 + 18 + 18, 200, 36), visible=False),
        item(f"kf_i_c{n}b", f"kf_c{n}b", geom(96 + CHIP_W / 2, y0 + 18 + 36 + 8 + lines * 22 * 1.4 / 2,
                                               CHIP_W - 48, lines * 22 * 1.4), visible=False),
    ]
scene("s_kf", "Tour 3 · Keyframes", kf_items, labels=LABEL, folder="f_tour")
kf_layouts = [
    ("Two-up", {"host": (500, 470, 880), "guest": (1420, 470, 880), "slide": (960, 500, 900),
                "lower": (470, 940, 760)}, {"slide"}),
    ("Close-up", {"host": (960, 540, 1760), "guest": (1610, 830, 440), "slide": (960, 500, 900),
                  "lower": (470, 940, 760)}, {"slide", "lower"}),
    ("Main feed", {"slide": (960, 540, 1800), "host": (1640, 230, 380), "guest": (1640, 470, 380),
               "lower": (470, 940, 760)}, {"lower"}),
]
K_KF = []
for n, (kname, places, hide) in enumerate(kf_layouts):
    ov = {"kf_i_hl0": {"item_id": "kf_i_hl0", "visible": False},
          f"kf_i_hl{n + 1}": {"item_id": f"kf_i_hl{n + 1}", "visible": True}}
    for part, (cx, cy, w) in places.items():
        o = {"item_id": f"kf_i_{part}", "geometry": part_geom(part, cx, cy, w)}
        if part in hide:
            o["visible"] = False
        ov[o["item_id"]] = o
    if n == 1:  # the picture-in-picture lands a beat after the close-up
        ov["kf_i_guest"]["timing"] = {"delay_ms": 250}
    for part in ("", "t", "b"):
        ov[f"kf_i_c{n}{part}"] = {"item_id": f"kf_i_c{n}{part}", "visible": True}
    scene(f"s_kf_k{n}", kname, [], variant_of="s_kf", overrides=[ov[k] for k in sorted(ov)])
    K_KF.append(f"s_kf_k{n}")

# ---------------------------------------------------------------- Motion (live: this chapter is the feature)
text_src("mo_h", "Motion: headline", "Items that move on their own", 60, face="bold")
text_src("mo_b", "Motion: body", "Motion modifiers move an item's position, scale, rotation, opacity or an effect setting, with no keyframes. Scene cameras take them too.",
         28, color=TXT2, wrap_width=1100)
mo_cards = [
    ("wiggle", "Wiggle", "Seeded noise", [mod("wx", "x", "wiggle", amplitude=26.0, frequency_hz=0.7, seed=1, octaves=2),
                                          mod("wy", "y", "wiggle", amplitude=20.0, frequency_hz=0.6, seed=2, octaves=2)]),
    ("osc", "Oscillate", "A waveform", [mod("rock", "rotation", "oscillate", amplitude=14.0, period_ms=2400, shape="sine")]),
    ("drift", "Drift", "A steady rate", [mod("turn", "rotation", "drift", rate_per_s=40.0, wrap=360.0)]),
    ("impulse", "Impulse", "Fired by a cue", [mod("kick", "scale", "impulse", clock="triggered", amplitude=0.35,
                                                  frequency_hz=5.0, decay_per_s=3.0, duration_ms=1600)]),
    ("audio", "Audio", "Follows a sound level", [mod("pulse", "scale", "audio", measure="level", floor_db=-48.0,
                                                     ceiling_db=-6.0, attack_ms=20, release_ms=300, from_=0.0, to=0.3)]),
]
mo_items = backdrop_items("mo") + eyebrow("mo", 4, "Motion", 96, 200) + [
    item("mo_i_h", "mo_h", geom(96 + 480, 280, 960, 80)),
    item("mo_i_bb", "mo_b", geom(96 + 560, 380, 1120, 90)),
]
MC_W, MC_GAP = 300, 57
shape_src("mo_card", "Motion: card", MC_W, 360, T["panel"], radius=12.0, border_width=1.0, border_color=T["border"])
shape_src("mo_sample", "Motion: sample", 96, 96, ACCENT + "29", radius=14.0, border_width=2.0, border_color=ACCENT_A)
for n, (k, t_, sub, mods) in enumerate(mo_cards):
    x = 96 + MC_W / 2 + n * (MC_W + MC_GAP)
    text_src(f"mo_{k}_t", f"Motion: {t_}", t_, 28, face="bold", align="center")
    text_src(f"mo_{k}_s", f"Motion: {t_} (text)", sub, 22, color=TXT2, align="center")
    mo_items += [
        item(f"mo_i_{k}_card", "mo_card", geom(x, 720, MC_W, 360, fit="stretch"), effects=[popout_shadow()]),
        item(f"mo_i_{k}", "mo_sample", geom(x, 660, 96, 96, fit="stretch"), motion=mods),
        item(f"mo_i_{k}_t", f"mo_{k}_t", geom(x, 816, MC_W - 32, 36)),
        item(f"mo_i_{k}_s", f"mo_{k}_s", geom(x, 852, MC_W - 32, 30)),
    ]
scene("s_motion", "Tour 4 · Motion", mo_items, labels=LABEL, folder="f_tour")

# ---------------------------------------------------------------- Connected: a DAW and web pages
text_src("ln_h", "Connected: headline", "Your DAW and your web pages, in the loop", 60, face="bold")
ln_cards = [
    ("JTunnel from the DAW", "JTunnel, a CLAP plugin, sends a track's audio and MIDI over the local network. JStream takes the audio as a source and the MIDI as bindings."),
    ("Live data from Bitwig", "In Bitwig, JTunnel also sends the clip grid, the transport and the device, and that data can drive values in a scene."),
    ("Pages that read JStream", "A browser source's page can be granted the clock, scene names, shared values, audio levels, tempo, MIDI and DAW data, each by its own switch."),
]
LC_W, LC_GAP = 520, 84
ln_items = backdrop_items("ln") + [
    item("ln_i_light", "soft_light", geom(1382, 410, 1200, 700, fit="stretch"), blend="additive"),
] + eyebrow("ln", 8, "Connected", 96, 220) + [item("ln_i_h", "ln_h", geom(96 + 640, 300, 1280, 80))]
for n, (t_, b_) in enumerate(ln_cards):
    x0 = 96 + n * (LC_W + LC_GAP)
    shape_src(f"ln_c{n}", f"Connected: card {n + 1}", LC_W, 380, T["panel"], radius=12.0, border_width=1.0,
              border_color=T["border"])
    shape_src(f"ln_c{n}m", f"Connected: card {n + 1} mark", 32, 3, ACCENT_A)
    text_src(f"ln_c{n}t", f"Connected: card {n + 1} title", t_, 32, face="bold")
    text_src(f"ln_c{n}b", f"Connected: card {n + 1} text", b_, 24, color=TXT2, wrap_width=LC_W - 64)
    tw = min(LC_W - 64, text_w(t_, 32, "bold"))
    ln_items += [
        item(f"ln_i_c{n}", f"ln_c{n}", geom(x0 + LC_W / 2, 650, LC_W, 380, fit="stretch"), visible=False,
             effects=[popout_shadow()]),
        item(f"ln_i_c{n}m", f"ln_c{n}m", geom(x0 + 48, 494, 32, 3, fit="stretch"), visible=False),
        item(f"ln_i_c{n}t", f"ln_c{n}t", geom(x0 + 32 + tw / 2, 536, tw, 44), visible=False),
        item(f"ln_i_c{n}b", f"ln_c{n}b", geom(x0 + LC_W / 2, 680, LC_W - 64, 200), visible=False),
    ]
    if n < 2:
        shape_src(f"ln_l{n}", f"Connected: link {n + 1}", LC_GAP - 24, 2, ACCENT_A)
        ln_items.append(item(f"ln_i_l{n}", f"ln_l{n}", geom(x0 + LC_W + LC_GAP / 2, 650, LC_GAP - 24, 2,
                                                            fit="stretch"), visible=False))
LN_PARTS = [[f"ln_i_c{n}{x}" for x in ("", "m", "t", "b")] + ([f"ln_i_l{n}"] if n < 2 else []) for n in range(3)]
ln_cues = [{"at_ms": 0, "action": act("item.hide", item_id=i)} for grp in LN_PARTS for i in grp]
ln_cues += [{"at_ms": 600 + n * 2400, "action": act("item.show", item_id=i)} for n, grp in enumerate(LN_PARTS)
            for i in grp]
ln_cues.sort(key=lambda c: c["at_ms"])
scene("s_link", "Tour 8 · Connected", ln_items, labels=LABEL, folder="f_tour",
      timelines=[{"timeline_id": "link_build", "name": "Connected build", "duration_ms": 6000, "loop": "once",
                  "cues": ln_cues}])

# ---------------------------------------------------------------- 4 Effects
K_FX = screenshot_chapter("s_fx", "Tour 4 · Effects", [("fx", "effects.jpg", 960, 540, 1600)], [
    ("Item effects", "fx", (0.74, 0.335, 0.995, 0.58), "Effects on one item",
     "Rounded corners and a drop shadow on this item only, applied live, in order.", "left"),
    ("Result", "fx", (0.265, 0.205, 0.705, 0.615), "Shader packs",
     "Beyond the built-in filters, shader sources and filters can be written as WGSL effect packs.", "right"),
])

# ---------------------------------------------------------------- 3D: one showcase, the cockpit
# JStream's own renders of StreamingScenes' cockpit-3d project (a glTF model in a 3D scene), and
# its DAW screens: browser-source pages drawing a simulated Bitwig session's JTunnel data.
K_3D = screenshot_chapter("s_3d", "Tour 7 · 3D cockpit", [
    ("ov", "cockpit-overhead.jpg", 760, 540, 1400), ("lf", "cockpit-left.jpg", 2260, 540, 1400),
    ("daw", "daw-screens.jpg", 3860, 540, 1600)], [
    ("Monitor", "lf", (0.67, 0.22, 1.0, 0.86), "A live picture on a 3D monitor",
     "Any 2D scene, such as a camera feed, plays on the model's monitor through the model's texture setting.", "left"),
    ("Bitwig", "daw", (0.0, 0.0, 1.0, 1.0), "Bitwig, live, over JTunnel",
     "The cockpit's screens are browser-source pages drawing Bitwig's live data. Here the session is simulated.", "below"),
    ("Fields", "daw", (0.0, 0.0, 0.67, 0.5), "What Bitwig sends",
     "Clock and tempo, transport, the clip grid and scenes, track meters, notes, mixer, device, clip and markers.", "below"),
    ("Mapped", "ov", (0.0, 0.62, 1.0, 1.0), "Mapped onto the scene",
     "Data modifiers map a field onto an item's position, opacity or settings: here the meters drive the cabin lights and glow.", "above"),
], base_cam=cam(760 + 0.1 * dist(1800), 540 - 0.04 * dist(1800), dist(1800), 760, 540))

# ---------------------------------------------------------------- 6 Sequences & channels
K_SEQ = screenshot_chapter("s_seq", "Tour 6 · Sequences & channels", [("sq", "sequence.jpg", 960, 540, 1600)], [
    ("Lanes", "sq", (0.0, 0.70, 0.995, 0.93), "Sequences move values over time",
     "Lanes move channels along curves; cues fire actions such as showing an item or loading a keyframe.", "above"),
    ("Triggers", "sq", (0.0, 0.67, 0.50, 0.715), "They can start themselves",
     "A sequence can start or stop on a channel rising, a keyframe loading, a scene showing, or a key.", "above"),
    ("Channel", "sq", (0.79, 0.33, 0.995, 0.56), "Channels: one number, many inputs",
     "MIDI, live data, keys, cues or a lane can move a channel; positions, cameras, effects and live settings follow it.", "left"),
])

# ---------------------------------------------------------------- 7 Keys & MIDI
K_KEYS = screenshot_chapter("s_keys", "Tour 7 · Keys & MIDI", [("km", "keys-midi.jpg", 960, 540, 1100)], [
    ("Binding", "km", (0.29, 0.345, 0.83, 0.41), "One binding system",
     "Hotkeys, MIDI controllers and tempo sync share it, and a key or pad can play a sequence of cues.", "below"),
    ("Explained", "km", (0.29, 0.22, 0.83, 0.30), "Bindings run ordinary actions",
     "A key or a pad runs the same actions the buttons do: switch scenes, load keyframes, play sequences, go live.", "below"),
])

# ---------------------------------------------------------------- 8 Plugins
K_PLUG = screenshot_chapter("s_plug", "Tour 8 · Plugins", [("pg", "plugin-grant.jpg", 960, 540, 1300)], [
    ("Access", "pg", (0.315, 0.375, 0.69, 0.58), "Plugins ask, you grant",
     "Automation plugins run sandboxed and get only the access their manifest asks for and you grant. An update that asks for more stays off until you grant it again.", "right"),
])

# ---------------------------------------------------------------- Cameras and going live (two panels)
K_CAM = screenshot_chapter("s_cam", "Tour 12 · Cameras & going live", [
    ("pz", "ptz-panel.jpg", 640, 540, 360), ("st", "stream-panel.jpg", 1260, 420, 560)], [
    ("Drive", "pz", (0.0, 0.0, 1.0, 0.36), "Drive real cameras",
     "Drive PTZ cameras from the panel, recall shots from a key, and map pan, tilt, zoom and focus to MIDI.", "right"),
    ("Presets", "pz", (0.0, 0.62, 1.0, 1.0), "Shots belong to scenes",
     "A scene can carry each camera's shot, so switching the scene aims the cameras.", "right"),
    ("Health", "st", (0.0, 0.0, 1.0, 0.36), "Health you can read",
     "Bitrate, dropped frames and a plain verdict on how the stream is doing.", "left"),
    ("Encoders", "st", (0.0, 0.42, 1.0, 1.0), "Settings per output",
     "Each stream or recording has its own encoder settings, video mix and audio bus.", "left"),
])

# ---------------------------------------------------------------- 11 Shows
K_SHOW = screenshot_chapter("s_show", "Tour 11 · Shows", [
    ("ed", "show-edit.jpg", 760, 540, 1400), ("bm", "bookmark-inspector.jpg", 1640, 540, 300),
    ("run", "show-run.jpg", 2560, 540, 1400)], [
    ("Tracks", "ed", (0.0, 0.55, 0.995, 0.90), "A show is the whole run order",
     "Program, overlay, keyframe, sequence and audio tracks on one timeline, saved with the project.", "above"),
    ("Loop", "ed", (0.115, 0.585, 0.36, 0.935), "Loops hold until you're ready",
     "A loop repeats a span, like a waiting room, until you press Continue.", "right"),
    ("Bookmarks", "ed", (0.11, 0.895, 0.995, 0.93), "Bookmarks pause or play through",
     "Jump to any bookmark and the studio is set as playing there would have left it.", "above"),
    ("Notes", "bm", (0.0, 0.0, 1.0, 1.0), "Notes for whoever runs it",
     "Each bookmark has a name, a pausing switch, an arrival transition, its own Go to key, and a note like this tour's talking points.", "left"),
    ("Continue", "run", (0.0, 0.475, 0.22, 0.80), "One button runs it",
     "Continue is an action like any other, so a key, a MIDI pad or a click can press it.", "right"),
    ("Run view", "run", (0.22, 0.475, 0.995, 0.76), "A view for show time",
     "Now and next, every bookmark as a button, and clocks against the planned length.", "below"),
], base_cam=cam(760 + 0.1 * dist(1800), 540 - 0.04 * dist(1800), dist(1800), 760, 540))

# ---------------------------------------------------------------- 12 Built differently
text_src("bd_h", "Built: headline", "Written from scratch, around one idea.", 60, face="bold")
pillars = [
    ("Everything is an API", "The app, the web UI and the command line are all clients of one protocol, so a script, or an AI agent over MCP, can drive almost anything a person can."),
    ("Rust core", "The real-time audio thread never allocates, locks or blocks, and tests enforce it."),
    ("Headless first", "The engine runs with no window, on a software GPU with a fake clock and fake devices. That is how its tests run."),
    ("Open source", "MIT or Apache-2.0; one codebase for Windows, macOS and Linux."),
]
bd_eb = eyebrow("bd", 13, "Under the hood", 96, 200)
bd_items = backdrop_items("bdf") + [
    item("bd_i_light", "soft_light", geom(1382, 410, 1200, 700, fit="stretch"), blend="additive"),
] + bd_eb + [
    item("bd_i_h", "bd_h", geom(96 + 620, 280, 1240, 80)),
]
CARD_W, CARD_GAP = 408, 24
for n, (t_, b_) in enumerate(pillars):
    x0 = 96 + n * (CARD_W + CARD_GAP)
    x = x0 + CARD_W / 2
    shape_src(f"bd_p{n}", f"Built: card {n + 1}", CARD_W, 400, T["panel"], radius=12.0,
              border_width=1.0, border_color=T["border"])
    shape_src(f"bd_p{n}m", f"Built: card {n + 1} mark", 32, 3, ACCENT_A)
    text_src(f"bd_p{n}t", f"Built: card {n + 1} title", t_, 32, face="bold", wrap_width=CARD_W - 64)
    text_src(f"bd_p{n}b", f"Built: card {n + 1} text", b_, 24, color=TXT2, wrap_width=CARD_W - 64)
    tw = min(CARD_W - 64, text_w(t_, 32, "bold"))
    bd_items += [item(f"bd_i_p{n}", f"bd_p{n}", geom(x, 640, CARD_W, 400, fit="stretch"), visible=False,
                      effects=[popout_shadow()]),
                 item(f"bd_i_p{n}m", f"bd_p{n}m", geom(x0 + 32 + 16, 474, 32, 3, fit="stretch"), visible=False),
                 item(f"bd_i_p{n}t", f"bd_p{n}t", geom(x0 + 32 + tw / 2, 516, tw, 44), visible=False),
                 item(f"bd_i_p{n}b", f"bd_p{n}b", geom(x, 660, CARD_W - 64, 220), visible=False)]
PARTS = ("", "m", "t", "b")
bd_cues = [{"at_ms": 0, "action": act("item.hide", item_id=f"bd_i_p{n}{x}")} for n in range(4) for x in PARTS]
bd_cues += [{"at_ms": 700 + n * 1200, "action": act("item.show", item_id=f"bd_i_p{n}{x}")}
            for n in range(4) for x in PARTS]
bd_cues.sort(key=lambda c: c["at_ms"])
scene("s_built", "Tour 12 · Built differently", bd_items, labels=LABEL, folder="f_tour",
      timelines=[{"timeline_id": "built_build", "name": "Built build", "duration_ms": 6000, "loop": "once",
                  "cues": bd_cues}])

# ---------------------------------------------------------------- 13 Thanks
text_src("th_brand", "Thanks: wordmark", "JStream", 120, face="bold", align="center", letter_spacing=-3.0)
text_src("th_line", "Thanks: line", "Thank you.", 48, color=TXT2, align="center")
text_src("th_url", "Thanks: link", "github.com/jeffmhopkins/JStream", 26, color=LINK, align="center",
         face="mono")
scene("s_thanks", "Tour 13 · Thanks", backdrop_items("th") + [
    item("th_i_light", "soft_light", geom(W / 2, 420, 1200, 700, fit="stretch"), blend="additive",
         motion=[mod("roam", "x", "oscillate", amplitude=40.0, period_ms=20000)]),
    item("th_i_brand", "th_brand", geom(W / 2, 440, 700, 150),
         effects=[fx("glow", "glow", color=ACCENT + "80", radius=40.0, strength=0.0)],
         motion=[mod("glow_amt", "effect", "channel", effect={"filter_id": "glow", "param": "strength"},
                     channel_id="glow", from_=0.0, to=0.5)]),
    item("th_i_line", "th_line", geom(W / 2, 560, 600, 64)),
    item("th_i_url", "th_url", geom(W / 2, 660, 700, 40)),
], labels=LABEL, folder="f_tour", timelines=[{
    "timeline_id": "outro_glow", "name": "Outro glow", "duration_ms": 12000, "loop": "loop", "cues": [],
    "lanes": [{"target": {"channel": "glow"}, "points": [
        {"at_ms": 0, "value": 0.1, "curve": "hold"},
        {"at_ms": 6000, "value": 0.8, "curve": "ease_in_out"},
        {"at_ms": 12000, "value": 0.1, "curve": "ease_in_out"}]}]}])

# ---------------------------------------------------------------- overlays
# The status tag, top right: a neutral "rendered in JStream" chip (no red: red means on air).
TAG = "RENDERED IN JSTREAM"
tag_tw = text_w(TAG, 18, "bold", 2.5)
tag_w = tag_tw + 24 + 9 + 12 + 20
text_src("bug_txt", "Status tag: text", TAG, 18, color=T["text_soft"], face="bold", letter_spacing=2.5)
shape_src("bug_plate", "Status tag: plate", tag_w, 40, "#1f232ad9", radius=8.0, border_width=1.0,
          border_color=T["border"])
shape_src("bug_dot", "Status tag: dot", 9, 9, T["ok"], shape="ellipse")
tag_x0 = W - 96 - tag_w
scene("s_bug", "Overlay · Status tag", [
    item("bug_i_plate", "bug_plate", geom(tag_x0 + tag_w / 2, 96 + 20, tag_w, 40, fit="stretch")),
    item("bug_i_dot", "bug_dot", geom(tag_x0 + 24 + 4.5, 116, 9, 9, fit="stretch")),
    item("bug_i_txt", "bug_txt", geom(tag_x0 + 24 + 9 + 12 + tag_tw / 2, 116, tag_tw, 26)),
], folder="f_overlays")
# The title's lower third.
LT_EB, LT_T, LT_L = "Feature tour", "JStream", "A live streaming studio"
lt_w = min(760, max(text_w(LT_T, 40, "bold"), text_w(LT_L, 24)) + 58)
lt_h = 20 + 18 * 1.3 + 8 + 40 * 1.15 + 6 + 24 * 1.35 + 22
lt_y0 = 984 - lt_h
shape_src("lt_bar", "Lower third: plate", lt_w, lt_h, T["panel86"], radius=10.0, border_width=1.0,
          border_color=T["border"])
shape_src("lt_rule", "Lower third: bar", 4, lt_h - 2, ACCENT_A)
text_src("lt_name", "Lower third: title", LT_T, 40, face="bold")
text_src("lt_role", "Lower third: line", LT_L, 24, color=TXT2)
lt_tw, lt_lw = text_w(LT_T, 40, "bold"), text_w(LT_L, 24)
scene("s_lower", "Overlay · Lower third", [
    item("lt_i_bar", "lt_bar", geom(96 + lt_w / 2, lt_y0 + lt_h / 2, lt_w, lt_h, fit="stretch"),
         effects=[popout_shadow()]),
    item("lt_i_rule", "lt_rule", geom(96 + 3, lt_y0 + lt_h / 2, 4, lt_h - 2, fit="stretch")),
] + eyebrow("lt", None, LT_EB, 96 + 26, lt_y0 + 20 + 12, size=18) + [
    item("lt_i_name", "lt_name", geom(96 + 26 + lt_tw / 2, lt_y0 + 20 + 18 * 1.3 + 8 + 23, lt_tw, 46)),
    item("lt_i_role", "lt_role", geom(96 + 26 + lt_lw / 2, lt_y0 + lt_h - 22 - 16, lt_lw, 32)),
], folder="f_overlays")
# The stinger: a dark, fast accent-line sweep (the only stinger in the tour; it shows the feature).
shape_src("sting_veil", "Sting: veil", W, H, "#0a0b0eff")
shape_src("sting_line", "Sting: line", 3, H + 200, ACCENT_A)
scene("s_sting", "Sting · Sweep", [
    item("sting_i_veil", "sting_veil", geom(W / 2 + W, H / 2, W, H, fit="stretch"),
         motion=[mod("sweep", "x", "drift", clock="shown", rate_per_s=-6400.0)]),
    item("sting_i_line", "sting_line", geom(W + W, H / 2, 3, H + 200, fit="stretch"),
         motion=[mod("sweep", "x", "drift", clock="shown", rate_per_s=-6400.0)],
         effects=[fx("glow", "glow", color=ACCENT + "59", radius=28.0, strength=0.8)]),
], folder="f_overlays")

source("desk", "Desktop audio", "desktop_audio", {})

# ---------------------------------------------------------------- the show
S = 1000
FOCUS_MS = 5500


def shot_len(kfs):
    return 4 * S + FOCUS_MS * len(kfs) + 3 * S


chapters = [
    # key, scene, length, preset into it, lower third (number, eyebrow, title) or None
    ("holding", "s_hold", 20 * S, None, None),
    ("title", "s_title", 12 * S, "slow_fade", None),
    ("studio", "s_studio", shot_len(K_STUDIO), "fade", (1, "The studio", "One app, every source")),
    ("make", "s_make", 12 * S, "fade", (2, "What you make", "A broadcast, built in")),
    ("keyframes", "s_kf", shot_len(K_KF) + 2 * S, "fade", None),
    ("motion", "s_motion", 16 * S, "fade", None),
    ("sequences", "s_seq", shot_len(K_SEQ), "fade", (5, "Sequences", "Sequences and channels")),
    ("shows", "s_show", shot_len(K_SHOW), "sting", (6, "Shows", "Run the whole show")),
    ("cockpit", "s_3d", shot_len(K_3D), "slow_fade", (7, "3D scenes", "A glTF cockpit, rendered in JStream")),
    ("connected", "s_link", 16 * S, "fade", None),
    ("keys", "s_keys", shot_len(K_KEYS), "fade", (9, "Control", "Keys, pads and MIDI")),
    ("effects", "s_fx", shot_len(K_FX), "fade", (10, "Effects", "Filters and effects")),
    ("plugins", "s_plug", shot_len(K_PLUG), "fade", (11, "Extend", "Plugins, with permission")),
    ("cameras", "s_cam", shot_len(K_CAM), "fade", (12, "Cameras & going live", "PTZ cameras, streaming, recording")),
    ("built", "s_built", 14 * S, "fade", None),
    ("thanks", "s_thanks", 20 * S, "slow_fade", None),
]
for key, sid, ln, pre, cap in chapters:
    if cap:
        caption(key, *cap)
kfs_of = {"cockpit": K_3D, "studio": K_STUDIO, "keyframes": K_KF, "effects": K_FX, "sequences": K_SEQ,
          "keys": K_KEYS, "plugins": K_PLUG, "cameras": K_CAM, "shows": K_SHOW}
preset_of = {"keyframes": "layout"}

starts, program, t = {}, [], 0
for key, sid, ln, pre, cap in chapters:
    starts[key] = t
    c = {"clip_id": f"c_{key}", "scene_id": sid, "length_ms": ln}
    if pre:
        c["preset_id"] = pre
    program.append(c)
    t += ln
END = t

keyframes = []
for key, kfs in kfs_of.items():
    t0 = starts[key] + 4 * S
    for n, kf in enumerate(kfs):
        keyframes.append({"marker_id": f"k_{key}_{n}", "at_ms": t0 + n * FOCUS_MS, "keyframe_id": kf,
                          "preset_id": preset_of.get(key, "glide")})
    keyframes.append({"marker_id": f"k_{key}_home", "at_ms": t0 + len(kfs) * FOCUS_MS,
                      "preset_id": preset_of.get(key, "glide")})
keyframes += [
    {"marker_id": "k_title_push", "at_ms": starts["title"] + 1 * S, "keyframe_id": "s_title_push",
     "preset_id": "drift"},
]
keyframes.sort(key=lambda k: k["at_ms"])

NOTES = {
    "preshow": "*Holding slate. It loops until you press Continue.*\n\n"
               "Hi everyone, we'll start in just a moment.\n\n"
               "*Check your sound and the stream health, then press Continue.*",
    "title": "This is JStream. It's a live streaming and compositing studio, written from scratch in Rust. "
             "It does the job of a studio like OBS: scenes, sources, mixing, streaming and recording.\n\n"
             "It's pre-release, and the show features you're about to see arrive in the next pre-release.\n\n"
             "And everything you're watching right now is a JStream project, run by a JStream show. "
             "None of it is a video.",
    "studio": "Here's the studio. A scene is a stack of sources: cameras, screen and window capture, media, "
              "browser pages, text, timers and audio visualisers. They're composited on the GPU, and every "
              "item can be cropped, turned in 3D, blended and given effects, live.\n\n"
              "Edits undo per client. My undo never takes back a change somebody else made, from a browser, "
              "the command line or an agent.\n\n"
              "And outputs take video mixes and audio buses, not scenes, so the stream and the recording "
              "can carry different pictures and sound.",
    "make": "Here's the kind of scene you can make. This is a live JStream scene, not a picture of one.\n\n"
            "Every piece is a built-in source: the feeds are images, cropped to 16:9 in the scene, the clock "
            "is a timer, and the lower third is a scene of its own, shown here as one layer.\n\n"
            "*The footage is from Tears of Steel, the Blender Foundation's open film, under CC BY.*",
    "keyframes": "Now the part I'm most excited about: keyframes.\n\n"
                 "This is one scene, called Mission feed. A keyframe is a saved arrangement of that same scene. "
                 "It can change where each item sits, its size, crop, opacity, whether it shows, and its "
                 "effects.\n\n"
                 "Watch: Two-up. Close-up. Main feed. Every item glides at once, and each item can have its own "
                 "delay. See the small picture land a beat late?\n\n"
                 "The show is loading these keyframes right now. A sequence, a hotkey or a MIDI pad can load "
                 "them too.",
    "motion": "Items can also move on their own, with no keyframes at all. These are motion modifiers.\n\n"
              "Wiggle is seeded noise. Oscillate follows a waveform. Drift is a steady rate. Impulse fires "
              "on a cue, and the show is kicking it right now. Audio follows a sound level.\n\n"
              "MIDI, live data and channels can drive them too. They work on position, scale, rotation, "
              "opacity and effect settings, and on scene cameras.",
    "sequences": "Sequences move values over time.\n\n"
                 "A channel is one number. MIDI, live data, keys, cues or a lane on a sequence can move it, "
                 "and positions, cameras, effects and live settings can follow it.\n\n"
                 "A sequence has lanes, which are curves on channels, and cues, which are actions on a clock. "
                 "It can even start itself: when a channel rises, a keyframe loads, a scene shows, or you "
                 "press a key.",
    "shows": "And this is what's running the whole presentation: a show.\n\n"
             "One timeline, with program, overlay, keyframe, sequence and audio tracks, saved with the "
             "project. Bookmarks pause or play through. Loops hold, like a waiting room, until I press "
             "Continue.\n\n"
             "I can jump to any bookmark, and the studio is set the way playing there would have left it.\n\n"
             "And the notes I'm reading right now? They're this bookmark's note.",
    "cockpit": "Scenes can be 3D. It's opt in, per scene: give a scene a camera and its items get depth. "
               "Most scenes stay 2D.\n\n"
               "Here's one example, a glTF cockpit rendered in JStream. Any 2D scene, like a camera feed, "
               "can play on the model's monitor.\n\n"
               "The screens show Bitwig, live, over JTunnel. Here the session is simulated. Bitwig sends "
               "the clock and tempo, transport, clip grid and scenes, track meters, notes, mixer, device, "
               "clip and markers. Pages draw it, and data modifiers map any of it onto the scene. Here the "
               "meters drive the cabin lights.",
    "connected": "JStream connects to your music setup.\n\n"
                 "JTunnel is a CLAP plugin. It sends a track's audio and MIDI over the local network, and "
                 "JStream takes the audio as a source and the MIDI as bindings. You accept each sender first.\n\n"
                 "In Bitwig, JTunnel also sends the clip grid, transport and device. And a browser source's "
                 "page can read JStream's clock, scenes, levels, tempo, MIDI and DAW data, each behind its "
                 "own switch.",
    "keys": "Control works one way for everything. Hotkeys, MIDI controllers and tempo sync share one "
            "binding system.\n\n"
            "A key or a pad runs the same actions the buttons do: switch scenes, load keyframes, play "
            "sequences, go live.\n\n"
            "*This bookmark continues by itself after 12 seconds.*",
    "effects": "Effects, quickly. Built-in filters work on sources, items, scenes and outputs. And for "
               "anything beyond those, you can write shader sources and filters as WGSL effect packs.",
    "plugins": "Automation plugins run sandboxed. A plugin only gets the access its manifest asks for and "
               "you grant. And if an update asks for more, it stays off until you grant it again.",
    "cameras": "PTZ cameras: drive them from the panel, recall shots from a key, and map pan, tilt, zoom "
               "and focus to MIDI. A scene can carry each camera's shot, so switching the scene aims the "
               "cameras.\n\n"
               "Going live: RTMP or RTMPS to YouTube or any service with a stream key, a recording at the "
               "same time, and a virtual camera on Windows and Linux. Each stream or recording gets its own "
               "encoder, mix and bus.\n\n"
               "*The stats panel is from a test engine, so its numbers are illustrative.*",
    "built": "Under the hood.\n\n"
             "Everything is an API. The app is just one client of the protocol, so a script, the command "
             "line, or an AI agent over MCP can drive almost anything a person can.\n\n"
             "It's Rust, and the real-time audio thread never allocates, locks or blocks. Tests enforce "
             "that. It runs headless too. And it's open source, MIT or Apache-2.0.",
    "thanks": "Thank you! Happy to take questions.\n\n"
              "*The Outro loop finishes its pass when you press Continue. Then the show goes back to the "
              "Pre-show, ready to run again.*",
}
names = {"title": "Welcome", "studio": "The studio", "make": "What you make", "keyframes": "Keyframes",
         "motion": "Motion", "sequences": "Sequences & channels", "shows": "Shows", "cockpit": "3D cockpit",
         "connected": "DAW & web pages", "keys": "Keys & MIDI", "effects": "Effects", "plugins": "Plugins",
         "cameras": "Cameras & going live", "built": "Under the hood", "thanks": "Thanks"}
bookmarks = [{"bookmark_id": "preshow", "name": "Pre-show", "at_ms": 0, "pausing": False, "note": NOTES["preshow"]}]
for key, *_ in chapters[1:]:
    b = {"bookmark_id": key, "name": names[key], "at_ms": starts[key], "note": NOTES[key]}
    if key == "title":
        b["pausing"] = False  # the Pre-show loop's end: Continue leaves the loop into Welcome
    if key in ("make", "motion", "effects"):
        b["pausing"] = False  # plays straight on from the chapter before
    if key == "keys":
        b["continue_after_ms"] = 12000
    if key == "shows":
        b["preset_id"] = "sting"
    bookmarks.append(b)
for b in bookmarks:
    assert len(b["note"].encode()) <= 1024, (b["bookmark_id"], len(b["note"].encode()))

loops = [
    {"loop_id": "preshow_loop", "name": "Pre-show", "start_ms": 0, "end_ms": starts["title"], "leave": "at_once"},
    {"loop_id": "outro_loop", "name": "Outro", "start_ms": starts["thanks"] + 4 * S,
     "end_ms": starts["thanks"] + 16 * S, "leave": "finish_pass", "preset_id": "fade"},
]
# Each chapter's lower third holds over its establishing shot, gone before the first push-in.
cap_clips = [{"clip_id": f"cap_{key}", "scene_id": captions[key], "start_ms": starts[key] + 300,
              "length_ms": 3600, "fade_in_ms": 500, "fade_out_ms": 300}
             for key, sid, ln, pre, cap in chapters if cap]
overlays = [
    {"track_id": "v2", "name": "Chapter lower thirds", "clips": cap_clips},
    {"track_id": "v3", "name": "Title lower third", "clips": [
        {"clip_id": "lt_title", "scene_id": "s_lower", "start_ms": starts["title"] + 6 * S, "length_ms": 5 * S,
         "fade_in_ms": 500, "fade_out_ms": 300}]},
    {"track_id": "v4", "name": "Status tag", "clips": [
        {"clip_id": "bug", "scene_id": "s_bug", "start_ms": starts["studio"],
         "length_ms": starts["thanks"] - starts["studio"], "fade_in_ms": 600, "fade_out_ms": 300}]},
]
sequences = [
    {"track_id": "s1", "name": "Builds", "cues": [
        {"cue_id": "q_title", "at_ms": starts["title"] + 300, "action": act("timeline.play", timeline_id="title_build")},
        {"cue_id": "q_link", "at_ms": starts["connected"] + 300, "action": act("timeline.play", timeline_id="link_build")},
        {"cue_id": "q_built", "at_ms": starts["built"] + 300, "action": act("timeline.play", timeline_id="built_build")},
        {"cue_id": "q_outro", "at_ms": starts["thanks"], "action": act("timeline.play", timeline_id="outro_glow")},
    ]},
    {"track_id": "s2", "name": "Events", "cues": [
        {"cue_id": f"e_kick{n}", "at_ms": starts["motion"] + (4 + 4 * n) * S,
         "action": act("item.trigger_motion", item_id="mo_i_impulse", modifier_id="kick")} for n in range(3)
    ] + [
        {"cue_id": "e_glow_off", "at_ms": starts["thanks"] - 500,
         "action": act("channel.set_value", channel_id="glow", value=0.0, fade_ms=400)},
    ]},
]
audio = [{"track_id": "a1", "name": "Desktop audio", "clips": [
    {"clip_id": "a_title", "source_id": "desk", "start_ms": starts["title"], "length_ms": 12 * S,
     "fade_in_ms": 2000, "fade_out_ms": 3000, "gain_db": -8.0},
    {"clip_id": "a_motion", "source_id": "desk", "start_ms": starts["motion"], "length_ms": 16 * S,
     "fade_in_ms": 1000, "fade_out_ms": 1000, "gain_db": -12.0},
    {"clip_id": "a_thanks", "source_id": "desk", "start_ms": starts["thanks"], "length_ms": 20 * S,
     "fade_in_ms": 3000, "fade_out_ms": 3000, "gain_db": -10.0},
]}]

show = {
    "show_id": "tour", "name": "Feature tour", "program": program, "overlays": overlays, "keyframes": keyframes,
    "sequences": sequences, "audio": audio, "bookmarks": bookmarks, "loops": loops,
    "end": {"type": "go_to", "bookmark_id": "preshow"}, "preset_id": "fade", "next_monitor": "still",
    "planned_ms": 20 * 60 * S,
}
# The lightning tour: title, keyframes, cockpit, thanks, straight through, looping.
L_KF = shot_len(K_KF) + 2 * S
l_t = [0, 10 * S, 10 * S + L_KF, 10 * S + L_KF + shot_len(K_3D)]
show_short = {
    "show_id": "tour_lightning", "name": "Lightning tour (no pauses)",
    "program": [
        {"clip_id": "l1", "scene_id": "s_title", "length_ms": 10 * S},
        {"clip_id": "l2", "scene_id": "s_kf", "length_ms": L_KF, "preset_id": "fade"},
        {"clip_id": "l3", "scene_id": "s_3d", "length_ms": shot_len(K_3D), "preset_id": "slow_fade"},
        {"clip_id": "l4", "scene_id": "s_thanks", "length_ms": 10 * S, "preset_id": "sting"},
    ],
    "keyframes": [{"marker_id": f"lk{n}", "at_ms": l_t[1] + 4 * S + n * FOCUS_MS, "keyframe_id": kf,
                   "preset_id": "layout"} for n, kf in enumerate(K_KF)] +
                 [{"marker_id": "lk_home", "at_ms": l_t[1] + 4 * S + len(K_KF) * FOCUS_MS, "preset_id": "layout"}] +
                 [{"marker_id": f"lc{n}", "at_ms": l_t[2] + 4 * S + n * FOCUS_MS, "keyframe_id": kf,
                   "preset_id": "glide"} for n, kf in enumerate(K_3D)] +
                 [{"marker_id": "lc_home", "at_ms": l_t[2] + 4 * S + len(K_3D) * FOCUS_MS, "preset_id": "glide"}],
    "sequences": [{"track_id": "ls", "name": "Builds", "cues": [
        {"cue_id": "lq1", "at_ms": 0, "action": act("timeline.play", timeline_id="title_build")}]}],
    "bookmarks": [
        {"bookmark_id": "l_top", "name": "Welcome", "at_ms": l_t[0], "pausing": False,
         "note": "No pauses: this show plays straight through and loops, with the Next monitor live. "
                 "It shares its scenes with the Feature tour: one project, several shows."},
        {"bookmark_id": "l_kf", "name": "Keyframes", "at_ms": l_t[1], "pausing": False,
         "note": "One scene, three keyframes. The show loads each one with a Move."},
        {"bookmark_id": "l_3d", "name": "3D cockpit", "at_ms": l_t[2], "pausing": False,
         "note": "The glTF cockpit, rendered in JStream, with its DAW screens."},
        {"bookmark_id": "l_end", "name": "Thanks", "at_ms": l_t[3], "pausing": False,
         "note": "Then it loops back to the top."},
    ],
    "end": {"type": "loop"}, "next_monitor": "live",
}

chan = [{"channel_id": "glow", "name": "Glow", "default": 0.0, "rise_ms": 100, "fall_ms": 300}]
hotkeys = [
    {"chord": "Ctrl+Alt+Space", "action": act("show.continue")},
    {"chord": "Ctrl+Alt+KeyP", "action": act("show.play", show_id="tour")},
    {"chord": "Ctrl+Alt+Period", "action": act("show.stop")},
    {"chord": "Ctrl+Alt+BracketLeft", "action": act("show.back")},
    {"chord": "Ctrl+Alt+BracketRight", "action": act("show.skip")},
    {"chord": "Ctrl+Alt+KeyL", "action": act("overlay.toggle", scene_id="s_lower")},
    {"chord": "Ctrl+Alt+KeyB", "action": act("overlay.toggle", scene_id="s_bug")},
    {"chord": "Ctrl+Alt+KeyK", "action": act("item.trigger_motion", item_id="mo_i_impulse", modifier_id="kick")},
] + [{"chord": f"Ctrl+Alt+Digit{n}", "action": act("show.go_to_number", number=n)} for n in range(1, 9)] + [
    {"chord": "Ctrl+Alt+Digit0", "action": act("show.go_to", show_id="tour", bookmark_id="thanks")}]
for h in hotkeys:
    h["labels"] = LABEL
bindings = [
    {"trigger": {"kind": "midi_note", "note": 36}, "action": act("show.continue")},
    {"trigger": {"kind": "midi_note", "note": 37}, "action": act("show.back")},
    {"trigger": {"kind": "midi_note", "note": 38}, "action": act("show.skip")},
    {"trigger": {"kind": "midi_note", "note": 39}, "action": act("overlay.toggle", scene_id="s_lower")},
]
transitions = {"presets": [
    {"id": "cut", "name": "Cut", "kind": "cut", "kind_version": 1, "duration_ms": 0, "easing": "linear"},
    {"id": "fade", "name": "Fade", "kind": "fade", "kind_version": 1, "duration_ms": 550, "easing": E_STD},
    {"id": "slow_fade", "name": "Slow fade", "kind": "fade", "kind_version": 1, "duration_ms": 1000,
     "easing": E_STD},
    {"id": "glide", "name": "Glide", "kind": "move", "kind_version": 1, "duration_ms": 1300, "easing": E_GLIDE,
     "settings": {"camera_path": "line", "stagger_ms": 0, "unmatched": "fade"}},
    {"id": "layout", "name": "Layout move", "kind": "move", "kind_version": 1, "duration_ms": 1000,
     "easing": E_GLIDE, "settings": {"camera_path": "line", "stagger_ms": 60, "unmatched": "fade"}},
    {"id": "drift", "name": "Drift", "kind": "move", "kind_version": 1, "duration_ms": 10000, "easing": "linear",
     "settings": {"camera_path": "line", "stagger_ms": 0, "unmatched": "fade"}},
    {"id": "sting", "name": "Sweep sting", "kind": "stinger", "kind_version": 1, "duration_ms": 600,
     "easing": "linear", "settings": {"scene": {"type": "scene", "scene_id": "s_sting"}, "cut_ms": 300}},
], "default": "fade"}

# ---------------------------------------------------------------- text boxes at their true size
# A text source draws a box as wide as its wrap width (or its widest line) and one line
# height (ascent + descent) plus a line step per extra line. An item box of another size
# scales the text, so every text item gets its source's real box, keeping its left edge
# (or centre, or right edge, by the text's alignment).
from PIL import ImageFont

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(OUT)), "fonts")


def text_box(st):
    f = ImageFont.truetype(os.path.join(FONT_DIR, os.path.basename(st["font"]["path"])), int(round(st["size"])))
    asc, desc = f.getmetrics()
    ls = st.get("letter_spacing", 0.0)
    wrap = st.get("wrap_width")
    width = lambda t: f.getlength(t) + ls * len(t)
    lines = []
    for para in st["text"].split("\n"):
        if not wrap:
            lines.append(para)
            continue
        cur = ""
        for word in para.split(" "):
            trial = (cur + " " + word) if cur else word
            if width(trial) > wrap and cur:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    w = wrap if wrap else max(width(l) for l in lines)
    lh = asc + desc
    return w, lh * len(lines) * 1.0 + (len(lines) - 1) * 0.0


SRC_BY_ID = {x["id"]: x for x in sources}
for sc in scenes:
    for it in sc.get("items", []):
        src = SRC_BY_ID[it["source_id"]]
        if src["kind"].get("kind") != "text":
            continue
        st = src["settings"]
        w, h = text_box(st)
        k = TEXT_SCALE.get(it["id"], 1.0)
        w, h = w * k, h * k
        g = it["geometry"]
        ow = g["size"]["width"]
        cx = g["center"]["x"]
        if st.get("align", "left") == "left":
            cx = cx - ow / 2 + w / 2
        elif st["align"] == "right":
            cx = cx + ow / 2 - w / 2
        g["center"]["x"] = float(round(cx, 2))
        g["size"] = {"width": float(round(w, 2)), "height": float(round(h, 2))}

doc = {
    "schema_version": 22, "rev": 1, "canvas": {"width": W, "height": H},
    "scenes": scenes, "sources": sorted(sources, key=lambda s: s["id"]), "outputs": [],
    "folders": [{"id": "f_tour", "name": "Feature tour"}, {"id": "f_overlays", "name": "Tour overlays"}],
    "labels": [{"id": "tour", "name": "Feature tour", "color": "#4c8dff"}],
    "hotkeys": sorted(hotkeys, key=lambda h: h["chord"]), "bindings": bindings, "channels": chan,
    "shows": [show, show_short], "transitions": transitions,
}


def fix(o):
    if isinstance(o, dict):
        return {("from" if k == "from_" else k): fix(v) for k, v in o.items() if v is not None}
    if isinstance(o, list):
        return [fix(v) for v in o]
    return o


with open(OUT, "w") as f:
    json.dump(fix(doc), f, indent=2, ensure_ascii=False)
    f.write("\n")
print(f"wrote {OUT}: {len(scenes)} scenes, {len(sources)} sources, show {END // 60000}:{END // 1000 % 60:02d}, "
      f"{len(keyframes)} keyframe markers")
