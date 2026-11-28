"""A heavy, fast-changing Bitwig session over JTunnel, to load-test JStream and its pages.

It stands in for the JTunnel plugin (and the Bitwig extension behind it) on one UDP port,
and sends far more than a real session does, all of it moving: a 32 x 32 clip grid whose
every slot changes state, every track's meter and held notes, dense MIDI in the audio
stream, the selected device's controls, the mixer, the markers, scene launches and track
selections, tempo sweeps, transport stops and loop jumps, and the 32 modulation params
(Mods 1 to 25 by default) moving every tick. The keys are in the shapes the extension and
the plugin send (Jclap plugins/jtunnel/bitwig/JTunnel.control.js, src/state.cpp), and the
wire is the plugin's own (src/protocol.h, src/state.cpp): each key's message ID is the
version it was set at, what changed goes at once, and the whole store goes again a slice at
a time about once a second, repeating each message's ID, as `StateBroadcaster::collect`
does. Beside the state it sends an audio stream (24-bit PCM, or MIDI only) with notes in
it, so the receive thread's playout and MIDI paths are loaded too.

    python stress.py [--port 47251] [--rate 30] [--tracks 32] [--scenes 32] [--automated 8]
                     [--mods 25] [--notes 6] [--audio pcm|midi|none] [--seconds 0] [--level 1]

It binds `--port` on 127.0.0.1 (47251, where JStream's `--jtunnel-accept Bitwig@127.0.0.1:47251`
expects Bitwig's JTunnel), so close Bitwig (or take JTunnel off its track) first; with
`--host 0.0.0.0` it also serves a receiver on another machine. JStream needs no change: it
subscribes to the port as it would to Bitwig, and the stress answers it. Every 5 s it prints
what it sent (keys, packets and kilobytes a second) and how far behind its own schedule it
ran, so a slow sender isn't taken for a slow receiver.

`--level` scales the tick rate, the notes and the automated tracks at once: 1 (the default)
is a very heavy real session at the extension's own 30 ticks a second, 2 twice that, and
`--level 4` (120 ticks, every track automated) is far past anything Bitwig sends. Ctrl+C
stops it; a receiver notices the silence, as when a sender stops.
"""
import argparse
import json
import math
import random
import socket
import struct
import sys
import threading
import time

MAGIC = b"JTUN"
VERSION = 2
PIECE = 1200          # the state bytes in one packet (kStatePieceBytes)
MAX_PIECES = 64
REFRESH_S = 1.0       # the whole store goes again about once a second
NAMES = ["Kick", "Snare", "Hats", "Perc", "Bass", "Sub", "Keys", "Pad", "Lead", "Arp", "Pluck",
         "Strings", "Brass", "Choir", "FX", "Vox"]
COLORS = ["#ff7a1a", "#ffc23d", "#2fd27a", "#3aa0ff", "#c45cff", "#ff4f9a", "#5ce1e6", "#e6e65c",
          "#ff5c5c", "#8cff5c", "#5c8cff", "#ff5ce1"]
DEVICES = [("Polysynth", "Synth"), ("Drum Machine", "Drums"), ("Phase-4", "Synth"),
           ("Sampler", "Sampler"), ("FM-4", "Synth"), ("Grid", "Modular")]
STATES = ["stopped", "playing", "recording", "stopped", "playing"]


def r(v, d=3):
    return round(float(v), d)


def wave(t, f, phase=0.0):
    """0 to 1, a sine at f Hz."""
    return 0.5 + 0.5 * math.sin(2 * math.pi * f * t + phase)


class Session:
    """Every key, all of them moving: `state(t)` at wall time t."""

    def __init__(self, tracks, scenes, mods, notes, automated, fx=8, markers=32, seed=7):
        self.tracks, self.scenes, self.mods, self.notes, self.fx = tracks, scenes, mods, notes, fx
        self.automated = automated
        self.markers = markers
        self.rng = random.Random(seed)
        self.beats = 0.0
        self.last_t = None
        self.playing = True
        self.launches = 0
        self.selects = 0
        self.launch = {"count": 0, "scene": -1, "name": "", "clips": 0, "lastScene": -1, "lastName": ""}
        self.select = {"count": 0, "track": -1, "name": "", "lastTrack": -1, "lastName": ""}
        self.launch_at = self.select_at = -10.0
        self.next_launch = 2.0
        self.next_select = 1.0
        self.held = [[] for _ in range(tracks)]  # [pitch, velocity, until beats]

    def tempo(self, t):
        # 90 to 150 BPM, a sweep every 40 s, with a wobble.
        return r(120 + 30 * math.sin(2 * math.pi * t / 40) + 2 * math.sin(2 * math.pi * t * 0.7), 2)

    def advance(self, t):
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        # The transport stops for 1.5 s every 45 s, and the loop jumps back 16 beats every 20 s:
        # the pages' reset paths (the clock going back) run too.
        cycle = t % 45
        self.playing = not (40 <= cycle < 41.5)
        if self.playing:
            self.beats += dt * self.tempo(t) / 60
        if int(t / 20) != int((t - dt) / 20) and self.beats > 16:
            self.beats -= 16

    def track_notes(self, ti, t):
        """The notes held on track ti: up to `notes` at a time, a new one most ticks."""
        held = [n for n in self.held[ti] if n[2] > self.beats]
        if self.playing and len(held) < self.notes and self.rng.random() < 0.6:
            base = 36 + (ti * 5) % 48
            held.append([base + self.rng.randrange(24), self.rng.randrange(40, 128),
                         self.beats + self.rng.choice([0.125, 0.25, 0.5, 1.0])])
        self.held[ti] = held
        return [[n[0], n[1]] for n in held]

    def slot(self, ti, si, t, cur):
        h = (ti * 131 + si * 31) % 97
        has = (h % 5) != 0
        # Each slot changes state about every 0.5 to 2 s, out of step with the others.
        phase = int(t * (0.5 + (h % 4) * 0.5) + h)
        state = STATES[phase % len(STATES)] if has else "empty"
        queued = [None, "play", None, "stop", "record", None][(phase + ti) % 6] if has else None
        return {"scene": si, "name": f"{NAMES[ti % len(NAMES)]} {si + 1}" if has else "",
                "color": COLORS[(ti + si) % len(COLORS)] if has else "#000000", "hasContent": has,
                "state": state, "queued": queued, "selected": si == cur}

    def state(self, t):
        self.advance(t)
        b = self.beats
        tempo = self.tempo(t)
        bar = int(b // 4)
        inbar = b - bar * 4
        cur = int(b // 16) % self.scenes
        sel = int(t * 1.3) % self.tracks
        keys = {}
        keys["project"] = {"name": "JTunnel stress", "layout": ["ARRANGE", "MIX", "EDIT"][int(t / 10) % 3],
                           "engine": True, "host": "Bitwig Studio (stress) 6.0", "api": 18}
        keys["clock"] = {"available": True, "playing": self.playing, "recording": int(t / 15) % 2 == 1,
                         "looping": True, "tempo": tempo, "beats": r(b, 4), "seconds": r(b * 60 / tempo, 4),
                         "bar": bar + 1, "beat": int(inbar) + 1, "beatPhase": r(inbar - int(inbar)),
                         "timeSignature": [4, 4], "loop": [0, 64]}
        keys["transport"] = {
            "playing": self.playing, "recording": int(t / 15) % 2 == 1, "arrangerOverdub": int(t / 7) % 2 == 1,
            "launcherOverdub": int(t / 11) % 2 == 1,
            "automationWrite": {"mode": "latch", "arranger": int(t / 5) % 2 == 1, "launcher": False,
                                "overridden": int(t / 3) % 2 == 1},
            "loop": True, "loopStart": 0, "loopLength": 64, "punchIn": int(t / 9) % 2 == 1, "punchOut": False,
            "metronome": int(t / 4) % 2 == 1, "preRoll": "none", "fill": int(t * 2) % 7 == 0, "tempo": tempo,
            "tempoText": f"{tempo:.2f} BPM", "timeSignature": [4, 4], "position": r(b, 2),
            "positionText": f"{bar + 1}.{int(inbar) + 1}.{int((inbar % 1) * 4) + 1}.{int((inbar * 400) % 100):02d}",
            "seconds": r(b * 60 / tempo, 2), "playStart": 0, "launchQuantization": "1",
            "postRecordingAction": "off", "crossfade": r(wave(t, 0.1))}
        keys["grid"] = {"tracks": self.tracks, "scenes": self.scenes, "trackOffset": 0, "sceneOffset": 0,
                        "trackCount": self.tracks, "sceneCount": self.scenes, "follow": "selection",
                        "selectedTrack": sel, "selectedScene": cur}
        keys["scenes"] = {"items": [{"index": i, "exists": True, "name": f"Scene {i + 1}",
                                     "color": "#ffd84a" if i == cur else COLORS[i % len(COLORS)],
                                     "clips": (i * 7) % self.tracks} for i in range(self.scenes)]}
        meters, notes = [], []
        for ti in range(self.tracks):
            lv = wave(t, 1.7 + ti * 0.13, ti) * (0.4 + 0.6 * wave(t, 4.1, ti * 0.7))
            meters.append([r(lv, 2), r(lv * (0.8 + 0.2 * wave(t, 3.3, ti)), 2)])
            notes.append(self.track_notes(ti, t))
            # The automated tracks' volume and pan move every tick, so their whole track key
            # (with its 32 slots) goes every tick, as Bitwig's automation makes it; the rest
            # step about once a second.
            at = t if ti < self.automated else math.floor(t)
            vol = wave(at, 0.05 + ti * 0.01, ti)
            pan = wave(at, 0.03 + ti * 0.007, ti * 2)
            keys[f"track/{ti}"] = {
                "index": ti, "exists": True, "name": f"{NAMES[ti % len(NAMES)]} {ti + 1}",
                "color": COLORS[ti % len(COLORS)], "type": "Instrument", "group": ti % 8 == 0,
                "selected": ti == sel, "armed": (ti + int(t / 3)) % 9 == 0, "monitor": "auto",
                "mute": (ti + int(t / 2)) % 11 == 0, "solo": (ti + int(t / 5)) % 17 == 0, "mutedBySolo": False,
                "active": True, "volume": r(vol), "volumeText": f"{20 * math.log10(max(vol, 1e-3)):.1f} dB",
                "pan": r(pan), "panText": f"{(pan - 0.5) * 200:+.0f}%", "stopped": not self.playing,
                "stopQueued": False, "playing": cur if self.playing else -1,
                "slots": [self.slot(ti, si, t, cur) for si in range(self.scenes)]}
        fx_meter = [[r(wave(t, 2.3 + i * 0.2, i), 2)] * 2 for i in range(self.fx)]
        master = max(m[0] for m in meters) if meters else 0
        keys["meters"] = {"tracks": meters, "fx": fx_meter, "master": [r(master, 2), r(master * 0.97, 2)]}
        keys["notes"] = {"tracks": notes, "master": [n for tn in notes for n in tn][:64]}

        def channel(name, color, i):
            v = wave(t, 0.08 + i * 0.01, i)
            return {"exists": True, "name": name, "color": color, "mute": False, "solo": False,
                    "mutedBySolo": False, "active": True, "volume": r(v), "volumeText": f"{v * 6 - 6:.1f} dB",
                    "pan": 0.5, "panText": "C"}
        keys["mixer"] = {"master": channel("Master", "#c0c0c0", 0),
                         "fx": [channel(f"FX {i + 1}", COLORS[i % len(COLORS)], i + 1) for i in range(self.fx)]}
        dev, cat = DEVICES[(sel // 4) % len(DEVICES)]
        params = []
        for pi in range(8):
            val = wave(t, 0.2 + pi * 0.11, pi)
            mod = min(1.0, val * (0.7 + 0.3 * wave(t, 5.0, pi)))
            params.append({"exists": True, "name": f"Macro {pi + 1}", "value": r(val), "modulated": r(mod),
                           "text": f"{val * 100:.1f} %"})
        keys["device"] = {"exists": True, "track": f"{NAMES[sel % len(NAMES)]} {sel + 1}",
                          "trackColor": COLORS[sel % len(COLORS)], "name": dev, "preset": f"{dev} {sel}",
                          "category": cat, "creator": "Bitwig", "enabled": True, "plugin": False,
                          "windowOpen": False, "pinned": False,
                          "page": {"index": int(t / 4) % 3, "name": ["Main", "Mod", "FX"][int(t / 4) % 3],
                                   "names": ["Main", "Mod", "FX"]},
                          "params": params,
                          "chain": [{"name": n, "enabled": True, "selected": i == 0}
                                    for i, n in enumerate([dev, "EQ+", "Compressor", "Delay+", "Reverb"])]}
        keys["clip"] = {"exists": True, "track": f"{NAMES[sel % len(NAMES)]} {sel + 1}", "scene": cur,
                        "name": f"Clip {sel}.{cur}", "color": COLORS[(sel + cur) % len(COLORS)],
                        "playing": self.playing, "playingStep": int((b % 16) * 4) if self.playing else -1,
                        "playStart": 0, "loopStart": 0, "loopLength": 16, "loop": True}
        keys["markers"] = {"items": [{"name": f"Marker {i + 1}", "position": i * 8,
                                      "color": "#ffd84a" if i == bar // 2 % self.markers else "#7f8ea3"}
                                     for i in range(self.markers)]}
        # A scene launch every ~2 s and a track selection every ~1 s, each held 0.3 s.
        if t >= self.next_launch:
            self.next_launch = t + 1.5 + self.rng.random()
            s = self.rng.randrange(self.scenes)
            self.launch.update(count=self.launch["count"] + 1, scene=s, name=f"Scene {s + 1}",
                               clips=self.rng.randrange(1, self.tracks + 1), lastScene=s, lastName=f"Scene {s + 1}")
            self.launch_at = t
        elif t - self.launch_at > 0.3 and self.launch["scene"] != -1:
            self.launch.update(scene=-1, name="")
        if t >= self.next_select:
            self.next_select = t + 0.7 + self.rng.random() * 0.6
            tr = self.rng.randrange(self.tracks)
            self.select.update(count=self.select["count"] + 1, track=tr, name=f"{NAMES[tr % len(NAMES)]} {tr + 1}",
                               lastTrack=tr, lastName=f"{NAMES[tr % len(NAMES)]} {tr + 1}")
            self.select_at = t
        elif t - self.select_at > 0.3 and self.select["track"] != -1:
            self.select.update(track=-1, name="")
        keys["launch"] = dict(self.launch)
        keys["select"] = dict(self.select)
        values = [r(wave(t, 0.3 + i * 0.09, i * 0.5), 6) if i < self.mods else 0.0 for i in range(32)]
        keys["params"] = {"values": values, "names": [""] * 32}
        keys["sender"] = {"tunnel": "JTunnel stress", "host": socket.gethostname(), "extension": True}
        return keys


class Sender:
    """The plugin's side of the wire on one port: state as `StateBroadcaster` sends it, an
    audio stream, and the subscriptions that say who gets them."""

    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 << 20)
        self.sock.bind((host, port))
        self.sock.settimeout(0.0)
        self.lock = threading.Lock()
        self.receivers = {}       # address -> when it last subscribed
        self.newcomer = False
        self.stream_id = int(time.time()) & 0x7FFFFFFF
        self.version = 0
        self.store = {}           # key -> [text, version]
        self.sent_version = 0
        self.refresh_carry = 0.0
        self.refresh_at = 0
        self.stats = {"keys": 0, "packets": 0, "bytes": 0, "audio": 0}

    def poll(self, now):
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except (BlockingIOError, socket.timeout, ConnectionResetError):
                break
            if len(data) < 6 or data[:4] != MAGIC or data[4] != VERSION:
                continue
            with self.lock:
                if data[5] == 2:
                    if addr not in self.receivers:
                        self.newcomer = True
                        print(f"receiver {addr[0]}:{addr[1]} subscribed", flush=True)
                    self.receivers[addr] = now
                elif data[5] == 3:
                    self.receivers.pop(addr, None)
        with self.lock:
            for addr in [a for a, seen in self.receivers.items() if now - seen > 2.0]:
                del self.receivers[addr]
                print(f"receiver {addr[0]}:{addr[1]} went quiet", flush=True)

    def to(self, packet):
        with self.lock:
            addrs = list(self.receivers)
        for addr in addrs:
            try:
                self.sock.sendto(packet, addr)
            except OSError:
                pass
        self.stats["packets"] += len(addrs)
        self.stats["bytes"] += len(packet) * len(addrs)

    def message(self, key, text, message_id):
        data = text.encode()
        pieces = max(1, math.ceil(len(data) / PIECE))
        if pieces > MAX_PIECES:
            return
        kb = key.encode()
        for p in range(pieces):
            chunk = data[p * PIECE:(p + 1) * PIECE]
            self.to(MAGIC + bytes([VERSION, 4]) + struct.pack("<IIBBB", self.stream_id, message_id & 0xFFFFFFFF,
                                                               p, pieces, len(kb)) + kb
                    + struct.pack("<H", len(chunk)) + chunk)
        self.stats["keys"] += 1

    def put(self, keys):
        for key, value in keys.items():
            text = json.dumps(value, separators=(",", ":"))
            was = self.store.get(key)
            if was is None or was[0] != text:
                self.version += 1
                self.store[key] = [text, self.version]

    def collect(self, tick_s):
        """What `StateBroadcaster::collect` sends: everything to a newcomer, else what changed,
        and a slice of the rest so the whole store goes again about once a second."""
        with self.lock:
            everything, self.newcomer = self.newcomer, False
        entries = sorted(self.store.items())
        if everything:
            for key, (text, v) in entries:
                self.message(key, text, v)
            self.sent_version = self.version
            self.refresh_at = 0
            return
        for key, (text, v) in entries:
            if v > self.sent_version:
                self.message(key, text, v)
        self.sent_version = self.version
        self.refresh_carry += len(entries) * tick_s / REFRESH_S
        while self.refresh_carry >= 1.0 and entries:
            self.refresh_carry -= 1.0
            if self.refresh_at >= len(entries):
                self.refresh_at = 0
            key, (text, v) = entries[self.refresh_at]
            self.refresh_at += 1
            self.message(key, text, v)


class Audio(threading.Thread):
    """The audio stream: 2 ms frames of 24-bit PCM at 48 kHz (a quiet tone), or 1 ms MIDI-only
    frames, each with its share of notes, two frames a packet (REDUNDANT on)."""

    def __init__(self, sender, kind, notes_per_s, stop):
        super().__init__(daemon=True)
        self.sender, self.kind, self.stop = sender, kind, stop
        self.rate = 48000
        self.samples = 96 if kind == "pcm" else 48
        self.codec = 1 if kind == "pcm" else 2
        self.frame_s = self.samples / self.rate
        self.notes_per_s = notes_per_s
        self.stream_id = (sender.stream_id + 1) & 0x7FFFFFFF
        self.rng = random.Random(3)
        self.on = []   # (channel, pitch, off at frame)
        self.phase = 0.0
        self.late_ms = 0.0

    def frame(self, n):
        events = []
        for ch, pitch, off in [x for x in self.on if x[2] <= n]:
            events.append((0, bytes([0x80 | ch, pitch, 0])))
            self.on.remove((ch, pitch, off))
        want = self.notes_per_s * self.frame_s
        count = int(want) + (1 if self.rng.random() < want - int(want) else 0)
        for _ in range(count):
            if len(events) >= 20:
                break
            ch, pitch = self.rng.randrange(16), self.rng.randrange(24, 108)
            events.append((self.rng.randrange(self.samples), bytes([0x90 | ch, pitch, self.rng.randrange(1, 128)])))
            self.on.append((ch, pitch, n + self.rng.randrange(20, 400)))
        if self.rng.random() < 0.3 and len(events) < 23:   # a CC now and then
            events.append((0, bytes([0xB0 | self.rng.randrange(16), self.rng.randrange(120), self.rng.randrange(128)])))
        body = bytes([len(events)])
        for off, ev in sorted(events, key=lambda e: e[0]):
            body += struct.pack("<H", off) + ev
        if self.kind == "pcm":
            out = bytearray()
            for i in range(self.samples):
                s = int(0.05 * 8388607 * math.sin(self.phase))
                self.phase += 2 * math.pi * 440 / self.rate
                b = struct.pack("<i", s)[:3]
                out += b + b
            self.phase %= 2 * math.pi
            body += struct.pack("<H", len(out)) + bytes(out)
        else:
            body += struct.pack("<H", 0)
        return body

    def run(self):
        n = 0
        prev = None
        start = time.perf_counter()
        while not self.stop.is_set():
            due = start + n * self.frame_s
            now = time.perf_counter()
            if now < due:
                time.sleep(min(0.002, due - now))
                continue
            self.late_ms = max(self.late_ms, (now - due) * 1000)
            body = self.frame(n)
            frames = [body] + ([prev] if prev is not None else [])
            packet = (MAGIC + bytes([VERSION, 1]) + struct.pack("<IIIBBHB", self.stream_id, n, self.rate, self.codec,
                                                                2, self.samples, len(frames)) + b"".join(frames))
            self.sender.to(packet)
            self.sender.stats["audio"] += 1
            prev = body
            n += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=47251)
    ap.add_argument("--rate", type=float, default=30, help="state ticks a second (the extension's is 30)")
    ap.add_argument("--automated", type=int, default=8,
                    help="tracks whose volume and pan move every tick (their whole key goes each tick)")
    ap.add_argument("--tracks", type=int, default=32)
    ap.add_argument("--scenes", type=int, default=32)
    ap.add_argument("--mods", type=int, default=25, help="how many of the 32 modulation params move")
    ap.add_argument("--notes", type=int, default=6, help="the most notes held on a track at once")
    ap.add_argument("--audio", choices=["pcm", "midi", "none"], default="pcm")
    ap.add_argument("--midi-notes", type=float, default=200, help="note-ons a second in the audio stream")
    ap.add_argument("--level", type=float, default=1.0, help="scales the rate and the notes")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this long (0: run until Ctrl+C)")
    a = ap.parse_args()
    a.tracks = max(1, min(32, a.tracks))
    a.scenes = max(1, min(32, a.scenes))
    rate = max(1.0, a.rate * a.level)
    notes = max(0, round(a.notes * a.level))
    sender = Sender(a.host, a.port)
    automated = max(0, min(a.tracks, round(a.automated * a.level)))
    session = Session(a.tracks, a.scenes, max(0, min(32, a.mods)), notes, automated)
    stop = threading.Event()
    audio = None
    if a.audio != "none":
        audio = Audio(sender, a.audio, a.midi_notes * a.level, stop)
        audio.start()
    print(f"JTunnel stress on {a.host}:{a.port}: {a.tracks} tracks x {a.scenes} scenes, {rate:g} ticks/s, "
          f"{automated} tracks automated, {a.mods} mods moving, up to {notes} notes a track, audio {a.audio}. "
          "Waiting for a subscribe.",
          flush=True)
    t0 = time.perf_counter()
    tick = 1.0 / rate
    n = 0
    last_report, behind, slow = t0, 0.0, 0
    base = dict(sender.stats)
    try:
        while True:
            due = t0 + n * tick
            now = time.perf_counter()
            if now < due:
                time.sleep(due - now)
                continue
            t = now - t0
            if a.seconds and t > a.seconds:
                break
            sender.poll(t)
            sender.put(session.state(t))
            sender.collect(tick)
            n += 1
            spent = time.perf_counter() - now
            if spent > tick:
                slow += 1
            behind = max(behind, (now - due) * 1000)
            if now - last_report >= 5.0:
                dt = now - last_report
                d = {k: (sender.stats[k] - base[k]) / dt for k in base}
                with sender.lock:
                    rx = len(sender.receivers)
                print(f"[{t:7.1f}s] {rx} receiver(s): {d['keys']:.0f} keys/s, {d['packets']:.0f} packets/s "
                      f"({d['audio']:.0f} audio), {d['bytes'] / 1024:.0f} KB/s; ticks over budget {slow}, "
                      f"most behind {behind:.1f} ms" + (f", audio most late {audio.late_ms:.1f} ms" if audio else ""),
                      flush=True)
                base, last_report, behind, slow = dict(sender.stats), now, 0.0, 0
                if audio:
                    audio.late_ms = 0.0
                # A sender this far behind its schedule skips ahead rather than bursting.
                if (time.perf_counter() - t0) - n * tick > 1.0:
                    n = int((time.perf_counter() - t0) / tick)
    except KeyboardInterrupt:
        pass
    stop.set()
    print("stopped", flush=True)


if __name__ == "__main__":
    main()
