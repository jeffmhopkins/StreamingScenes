#!/usr/bin/env python3
"""Writes storyboard.md from the feature-tour project file, so the storyboard always says
what the file holds: every chapter's time, shots, on-screen words and bookmark note.

    python3 make_storyboard.py feature-tour.json storyboard.md
"""
import json
import sys

d = json.load(open(sys.argv[1]))
SRC = {s["id"]: s for s in d["sources"]}
SCN = {s["id"]: s for s in d["scenes"]}
tour = next(s for s in d["shows"] if s["show_id"] == "tour")
PRESET = {p["id"]: p["name"] for p in d["transitions"]["presets"]}


def ts(ms):
    return f"{ms // 60000}:{ms // 1000 % 60:02d}"


def texts(scene_id, item_ids=None):
    out = []
    for it in SCN[scene_id]["items"]:
        if item_ids is not None and it["id"] not in item_ids:
            continue
        s = SRC[it["source_id"]]
        if s["kind"].get("kind") == "text":
            out.append(s["settings"]["text"].replace("\n", " "))
    return out


out = ["# Feature tour: storyboard", "",
       "Generated from `feature-tour.json` by `make_storyboard.py`, so it says what the project holds.",
       "Every picture is drawn live by JStream from the project: screenshots of the app are image",
       "sources, and every move is a keyframe loaded by the show. Nothing is a pre-rendered video.", "",
       f"Show **{tour['name']}**: {len(tour['program'])} clips, {ts(sum(c['length_ms'] for c in tour['program']))} "
       f"without pauses, {len(tour['bookmarks'])} bookmarks, {len(tour['loops'])} loops, "
       f"{len(tour['keyframes'])} keyframe markers, planned at {ts(tour['planned_ms'])}.", "",
       "Design: the app's own palette, IBM Plex, frameless windows with one shadow recipe, a spotlight and a",
       "menu-style chip per callout, glide easing on every camera move ([design-language.md](design-language.md)).", ""]
bms = {b["at_ms"]: b for b in tour["bookmarks"]}
caps = {c["start_ms"]: c for tr in tour["overlays"] for c in tr["clips"]}
t = 0
for clip in tour["program"]:
    sid = clip["scene_id"]
    sc = SCN[sid]
    b = bms.get(t, {})
    end = t + clip["length_ms"]
    out.append(f"## {ts(t)} · {b.get('name', sc['name'])}")
    out.append("")
    how = []
    how.append(f"scene `{sid}`, {clip['length_ms'] / 1000:g} s")
    if clip.get("preset_id"):
        how.append(f"in with {PRESET[clip['preset_id']]}")
    if b:
        if b.get("pausing", True):
            how.append("bookmark pauses here" + (f", continues by itself after {b['continue_after_ms'] / 1000:g} s"
                                                 if b.get("continue_after_ms") else ""))
        else:
            how.append("bookmark plays through")
        if b.get("preset_id"):
            how.append(f"arrives with {PRESET[b['preset_id']]}")
    out.append("*" + "; ".join(how) + "*")
    out.append("")
    base = texts(sid)
    vis_base = [t_ for it, t_ in zip([i for i in sc["items"] if SRC[i["source_id"]]["kind"].get("kind") == "text"], base)
                if it.get("visible", True)]
    if vis_base:
        out.append("On screen: " + " / ".join(f"“{x}”" for x in vis_base))
        out.append("")
    marks = [m for m in tour["keyframes"] if t <= m["at_ms"] < end]
    for m in marks:
        if m.get("keyframe_id"):
            kf = SCN[m["keyframe_id"]]
            shown = [o["item_id"] for o in kf.get("overrides", []) if o.get("visible") is True]
            words = texts(sid, set(shown))
            line = f"- {ts(m['at_ms'])} **{kf['name']}** ({PRESET[m['preset_id']]})"
            if words:
                line += ": " + " — ".join(words)
            out.append(line)
        else:
            out.append(f"- {ts(m['at_ms'])} back to the establishing shot ({PRESET[m['preset_id']]})")
    for tr in tour["overlays"]:
        for c in tr["clips"]:
            if t <= c["start_ms"] < end:
                words = texts(c["scene_id"])
                out.append(f"- {ts(c['start_ms'])} overlay {tr['track_id']}: " + " / ".join(words))
    for tr in tour["sequences"]:
        for c in tr["cues"]:
            if t <= c["at_ms"] < end:
                a = c["action"]
                out.append(f"- {ts(c['at_ms'])} cue on {tr['track_id']}: `{a['type']}` "
                           + " ".join(f"{k}={v}" for k, v in a.items() if k != "type"))
    for tr in tour["audio"]:
        for c in tr["clips"]:
            if t <= c["start_ms"] < end:
                out.append(f"- {ts(c['start_ms'])} audio: desktop audio at {c['gain_db']:g} dB for {c['length_ms'] / 1000:g} s")
    for lp in tour["loops"]:
        if t <= lp["start_ms"] < end:
            out.append(f"- {ts(lp['start_ms'])}–{ts(lp['end_ms'])} loop **{lp['name']}**, leaves "
                       + ("at once" if lp["leave"] == "at_once" else "after finishing its pass"))
    if b.get("note"):
        out.append("")
        out.append("> **Note for the presenter**")
        for line in b["note"].split("\n"):
            out.append("> " + line)
    out.append("")
    t = end
end = tour["end"]
out.append(f"## End\n\nThe show ends by going to the bookmark `{end.get('bookmark_id')}`, so it is ready to run again.\n")
light = next(s for s in d["shows"] if s["show_id"] == "tour_lightning")
out.append(f"## The second show: {light['name']}\n")
out.append(", then ".join(f"`{c['scene_id']}` ({c['length_ms'] / 1000:g} s)" for c in light["program"])
           + f". It loops, with the Next monitor live: one project, several shows, shared scenes.\n")
open(sys.argv[2], "w").write("\n".join(out))
print("wrote", sys.argv[2])
