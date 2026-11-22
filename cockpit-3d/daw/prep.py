"""Turns Jeff's funk song (v42, Jclap's demos/funk-song) into a DAW session timeline that
sim.py plays out as JTunnel state.

    python3 prep.py <Jclap demos/funk-song dir> <out session.json>

What comes from where:
- The arrangement, tempo and chords are v42's own (source/song.py's ARR, BPM, VERSE, CHORUS).
- The e-piano and lead notes, and the lead's breath, are v42's: song.py is run with its
  plugin renders stubbed out, so it writes the note lists it would have played
  (epiano.txt and lead.txt) and nothing else.
- The drums and bass are rendered by plugins this script doesn't have (JDrummer, JArp),
  so their notes come from the MP3: onsets in the kick, snare and hat bands, and the bass
  band's level on the chord's root.
- Each track's meter is its band of the MP3's spectrum, normalised; the master meter is
  the mix's own level, left and right.
"""
import json
import os
import runpy
import subprocess
import sys
import tempfile

import numpy as np

SRC, OUT = sys.argv[1:3]
V42 = os.path.join(SRC, "v42")
FPS = 30
BAR = 2.4  # 100 BPM, 4/4

# ---- v42's own note lists, from its song.py with the renders stubbed ----
work = tempfile.mkdtemp(prefix="funk-notes-")


class _Done:
    stdout = ""


_real_run = subprocess.run
subprocess.run = lambda *a, **k: _Done()
sys_argv = sys.argv
sys.argv = ["song.py", "/nonexistent", work, "kit", os.path.join(work, "out.mp3")]
song = {}
try:
    song = runpy.run_path(os.path.join(V42, "source", "song.py"), run_name="__main__")
except FileNotFoundError:
    pass  # it stops at the mix, which reads the renders; the note lists are written by then
finally:
    subprocess.run = _real_run
    sys.argv = sys_argv
# runpy loses the module's globals when it raises; read the arrangement from the source.
src = open(os.path.join(V42, "source", "song.py")).read()
ns = {}
for name in ("ARR", "VERSE", "CHORUS", "VERSE4", "BASS"):
    line = next(i for i, l in enumerate(src.splitlines()) if l.startswith(name + " ="))
    lines = src.splitlines()[line:]
    text, depth = "", 0
    for l in lines:
        text += l.split("#")[0] + "\n"
        depth += l.count("[") - l.count("]")
        if depth <= 0:
            break
    exec(text, {"E": [52, 62], "G": [55, 65], "A": [57, 67], "B": [59, 69], **ns}, ns)


def notes_from(path, channel_status):
    """(start, end, pitch, velocity) for each note on `channel_status` (0x90 | ch)."""
    on, out = {}, []
    for l in open(path):
        p = l.split()
        if len(p) < 4:
            continue
        t, st, k, v = float(p[0]), int(p[1]), int(p[2]), int(p[3])
        if st == channel_status and v > 0:
            on[k] = (t, v)
        elif st in (channel_status, channel_status - 0x10) and k in on:
            s, vel = on.pop(k)
            out.append([round(s, 3), round(t, 3), k, vel])
    return sorted(out)


keys_notes = notes_from(os.path.join(work, "epiano.txt"), 0x90)
lead_notes = notes_from(os.path.join(work, "lead.txt"), 0x91)
breath = []  # (t, 0..1): channel pressure on the lead's channel
for l in open(os.path.join(work, "lead.txt")):
    p = l.split()
    if int(p[1]) == 0xD1:
        breath.append((float(p[0]), int(p[2]) / 127))

# ---- the MP3 ----
raw = _real_run(["ffmpeg", "-loglevel", "error", "-i", os.path.join(V42, "funk-song-v42.mp3"),
                 "-ac", "2", "-ar", "48000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
x = np.frombuffer(raw, dtype="<f4").reshape(-1, 2)
SR = 48000
HOP = SR // FPS
N = 4096
dur = len(x) / SR
frames = int(dur * FPS)
win = np.hanning(N)
mono = x.mean(1)
pad = np.concatenate([np.zeros(N // 2), mono, np.zeros(N)])
freqs = np.fft.rfftfreq(N, 1 / SR)
BANDS = {"kick": (40, 110), "bass": (60, 260), "snare": (1500, 4500), "keys": (350, 1400),
         "lead": (700, 2800), "hats": (7000, 14000)}
band = {k: np.zeros(frames) for k in BANDS}
for i in range(frames):
    seg = pad[i * HOP:i * HOP + N]
    P = np.abs(np.fft.rfft(seg * win)) ** 2
    for k, (lo, hi) in BANDS.items():
        band[k][i] = P[(freqs >= lo) & (freqs < hi)].sum()


def level(e):
    """A band's energy as a 0..1 meter: dB over a 42 dB window under its loud end."""
    db = 10 * np.log10(e + 1e-12)
    top = np.percentile(db, 99)
    return np.clip((db - (top - 42)) / 42, 0, 1)


def onsets(e, k=1.6, gap=0.09):
    """Frames where a band's energy jumps: a crude onset detector, enough for lights."""
    d = np.log10(e + 1e-12)
    flux = np.maximum(0, np.diff(d, prepend=d[0]))
    thr = np.convolve(flux, np.ones(9) / 9, "same") * k + 0.05
    out, last = [], -99
    for i in range(1, len(flux) - 1):
        if flux[i] > thr[i] and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and i - last > gap * FPS:
            out.append(i)
            last = i
    return out


def master():
    out = []
    for i in range(frames):
        seg = x[i * HOP:i * HOP + HOP]
        r = np.sqrt((seg ** 2).mean(0) + 1e-12)
        out.append([float(np.clip((20 * np.log10(v) + 48) / 48, 0, 1)) for v in r])
    return out


def chord_root(bar):
    """The bass's root at a bar, from the chord chart its JArp parts hold."""
    for start, bars, _, chords in reversed(ns["BASS"]):
        if start <= bar < start + bars:
            rel = (bar - start) % 8
            root = chords[0][1][0]
            for at, c in chords:
                if at <= rel:
                    root = c[0]
            return root - 12
    return 40


lvl = {k: level(v) for k, v in band.items()}
drums_notes = []
for name, pitch in (("kick", 36), ("snare", 38), ("hats", 42)):
    for i in onsets(band[name]):
        t = i / FPS
        drums_notes.append([round(t, 3), round(t + 0.08, 3), pitch, int(60 + 67 * lvl[name][i])])
drums_notes.sort()
bass_notes = []
for i in onsets(band["bass"], k=1.3, gap=0.12):
    t = i / FPS
    bar = int(t // BAR)
    if bar < 49:
        bass_notes.append([round(t, 3), round(t + 0.2, 3), chord_root(bar), int(70 + 50 * lvl["bass"][i])])

sections = []
names = {0: "Intro", 1: "Verse", 3: "Chorus", 5: "Break"}
labels = ["Intro", "Verse 1", "Chorus 1", "Verse 2", "Break", "Chorus 2", "Pre-tag", "Tag"]
arr = ns["ARR"]
for i, (bar, _) in enumerate(arr):
    end = arr[i + 1][0] if i + 1 < len(arr) else 49
    sections.append({"name": labels[i], "bar": bar, "bars": end - bar})

session = {
    "title": "Funk song v42",
    "tempo": 100.0,
    "duration": round(dur, 3),
    "fps": FPS,
    "sections": sections,
    "notes": {"Drums": drums_notes, "Bass": bass_notes, "Keys": keys_notes, "Lead": lead_notes},
    "breath": [[round(t, 3), round(v, 3)] for t, v in breath[::2]],
    "levels": {k: [round(float(v), 3) for v in a] for k, a in lvl.items()},
    "master": [[round(a, 3), round(b, 3)] for a, b in master()],
}
json.dump(session, open(OUT, "w"), separators=(",", ":"))
print(f"wrote {OUT}: {dur:.1f} s, {len(keys_notes)} keys, {len(lead_notes)} lead, "
      f"{len(drums_notes)} drum and {len(bass_notes)} bass notes")
