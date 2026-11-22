"""A simulated Bitwig session, sent to JStream as real JTunnel state packets.

`Session(path)` plays prep.py's timeline of the funk song: `state(t)` is every key the
JTunnel Bitwig extension and the plugin's own clock would hold at song time `t`, in the
shapes they send (Jclap plugins/jtunnel/bitwig/JTunnel.control.js and src/state.cpp's
clockJson). `Tunnel` is the sender's side of the wire (src/protocol.h): it waits for a
receiver's subscribe and answers with state packets, split into pieces of at most 1,200
bytes. Run on its own, it plays the song in real time:

    python3 sim.py <session.json> [port]

and JStream receives it with `--jtunnel-accept Bitwig@127.0.0.1:<port>` (47251 by default).
"""
import json
import math
import socket
import struct
import sys
import time

TRACKS = [  # name, colour, device, preset, the scenes it has a clip in
    ("Drums", "#ff7a1a", "JKit", "Funk Kit (generated)", range(8)),
    ("Hats", "#ffc23d", "JKit", "Shaker Hats", range(8)),
    ("Bass", "#2fd27a", "JSynth", "Finger Bass", range(8)),
    ("Keys", "#3aa0ff", "JSynth", "Tine Piano", range(1, 8)),
    ("Lead", "#c45cff", "JBreath", "Alien Speech", range(2, 8)),
    ("Lead Echo", "#ff4f9a", "JBreath", "Alien Speech (wet)", [4]),
]
TRACK_SLOTS = 8  # columns shown; the ones past TRACKS don't exist
SCENES = 8
# Where the cursor (the selected track, and so the device and clip) sits in each section.
CURSOR = [0, 2, 4, 3, 5, 4, 2, 0]
PARAMS = {
    "JKit": [("Kick", 0.78), ("Snare", 0.72), ("Hats", 0.6), ("Clap", 0.4), ("Toms", 0.55),
             ("Crash", 0.5), ("Room", 0.35), ("Drive", 0.2)],
    "JSynth": [("Cutoff", 0.55), ("Resonance", 0.3), ("Env Amount", 0.6), ("Drive", 0.25),
               ("Attack", 0.05), ("Decay", 0.45), ("Glide", 0.1), ("Volume", 0.8)],
    "JBreath": [("Breath", 0.0), ("Alien Talk", 0.1), ("Alien Pace", 0.0), ("Unison", 0.0),
                ("Room", 0.45), ("Room Size", 0.7), ("Delay Mix", 0.14), ("Delay Feedback", 0.35)],
}
# Which level band moves each track's meter, and its notes.
BAND = {"Drums": "kick", "Hats": "hats", "Bass": "bass", "Keys": "keys", "Lead": "lead",
        "Lead Echo": "lead"}
NOTES = {"Drums": "Drums", "Hats": None, "Bass": "Bass", "Keys": "Keys", "Lead": "Lead",
         "Lead Echo": None}


def r(v, d=3):
    return round(float(v), d)


class Session:
    def __init__(self, path, pre_roll=2.0, post_roll=2.0):
        s = json.load(open(path))
        self.s = s
        self.tempo = s["tempo"]
        self.beat = 60.0 / self.tempo
        self.bar = 4 * self.beat
        self.pre = pre_roll
        self.length = s["duration"]
        self.end = pre_roll + self.length + post_roll
        self.sections = s["sections"]
        self.fps = s["fps"]
        self.notes = {k: sorted(v) for k, v in s["notes"].items()}
        self.breath = s["breath"]

    # ---- song position ----
    def song_time(self, t):
        return t - self.pre

    def playing(self, t):
        st = self.song_time(t)
        return 0.0 <= st < self.length

    def section_at(self, bar):
        idx = 0
        for i, sec in enumerate(self.sections):
            if bar >= sec["bar"]:
                idx = i
        return idx

    def level(self, name, st):
        a = self.s["levels"][name]
        i = int(st * self.fps)
        return a[i] if 0 <= i < len(a) else 0.0

    def breath_at(self, st):
        b = self.breath
        lo, hi = 0, len(b)
        while lo < hi:
            m = (lo + hi) // 2
            if b[m][0] <= st:
                lo = m + 1
            else:
                hi = m
        if lo == 0 or st - b[lo - 1][0] > 0.05:
            return 0.0
        return b[lo - 1][1]

    def sounding(self, track, st):
        out = []
        for s, e, k, v in self.notes.get(track, []):
            if s > st:
                break
            if st < e:
                out.append([k, v])
        return out

    # ---- the launcher ----
    def launcher(self, t):
        """(scene playing or -1, scene queued or -1) on the launcher at time t. Scenes
        launch on the bar, queued one bar ahead as Bitwig's default quantisation does."""
        st = self.song_time(t)
        if st < 0:
            # The pre-roll: scene 1 is queued once the transport is about to start.
            return -1, (0 if st > -1.2 else -1)
        if st >= self.length:
            return -1, -1
        bar = st / self.bar
        cur = self.section_at(int(bar))
        nxt = -1
        if cur + 1 < len(self.sections):
            nb = self.sections[cur + 1]["bar"]
            if nb - 1 <= bar < nb:
                nxt = cur + 1
        return cur, nxt

    def slot(self, ti, si, cur, nxt):
        name, color, _, _, scenes = TRACKS[ti]
        has = si in scenes
        state = "stopped" if has else "empty"
        queued = None
        if has and si == cur:
            state = "playing"
        if has and si == nxt:
            queued = "play"
        elif state == "playing" and nxt >= 0 and nxt not in scenes:
            queued = "stop"
        if cur == -1 and nxt == -1:
            pass
        sec = self.sections[si]["name"]
        return {"scene": si, "name": f"{name} {sec}" if has else "", "color": color if has else "#000000",
                "hasContent": has, "state": state, "queued": queued, "selected": False}

    # ---- every key ----
    def state(self, t):
        st = self.song_time(t)
        playing = self.playing(t)
        beats = max(0.0, st) / self.beat if st < self.length else self.length / self.beat
        bar_num = int(beats // 4)
        in_bar = beats - bar_num * 4
        cur, nxt = self.launcher(t)
        sec_i = self.section_at(bar_num) if st >= 0 else 0
        cursor = CURSOR[min(sec_i, len(CURSOR) - 1)]
        keys = {}
        keys["project"] = {"name": "Funk Song v42", "layout": "MIX", "engine": True,
                           "host": "Bitwig Studio (simulated) 6.0", "api": 18}
        keys["clock"] = {"available": True, "playing": playing, "recording": False, "looping": False,
                         "tempo": self.tempo, "beats": r(beats, 4), "seconds": r(max(0.0, min(st, self.length)), 4),
                         "bar": bar_num + 1, "beat": int(in_bar) + 1, "beatPhase": r(in_bar - int(in_bar)),
                         "timeSignature": [4, 4], "loop": [0, 0]}
        pos_text = f"{bar_num + 1}.{int(in_bar) + 1}.{int((in_bar % 1) * 4) + 1}.00"
        keys["transport"] = {
            "playing": playing, "recording": False, "arrangerOverdub": False, "launcherOverdub": False,
            "automationWrite": {"mode": "latch", "arranger": False, "launcher": False, "overridden": False},
            "loop": False, "loopStart": 0, "loopLength": 16, "punchIn": False, "punchOut": False,
            "metronome": False, "preRoll": "none", "fill": sec_i in (4,), "tempo": self.tempo,
            "tempoText": f"{self.tempo:.2f} BPM", "timeSignature": [4, 4], "position": r(beats, 2),
            "positionText": pos_text, "seconds": r(max(0.0, min(st, self.length)), 2), "playStart": 0,
            "launchQuantization": "1", "postRecordingAction": "off", "crossfade": 0.5}
        keys["grid"] = {"tracks": TRACK_SLOTS, "scenes": SCENES, "trackOffset": 0, "sceneOffset": 0,
                        "trackCount": len(TRACKS), "sceneCount": len(self.sections), "follow": "selection",
                        "selectedTrack": cursor, "selectedScene": max(cur, 0)}
        keys["scenes"] = {"items": [{"index": i, "exists": True, "name": sec["name"],
                                     "color": "#3a4658" if i != cur else "#ffd84a",
                                     "clips": sum(1 for tr in TRACKS if i in tr[4])}
                                    for i, sec in enumerate(self.sections)]}
        meters, notes = [], []
        for ti in range(TRACK_SLOTS):
            if ti >= len(TRACKS):
                keys[f"track/{ti}"] = {"exists": False, "name": "", "color": "#000000", "slots": [],
                                       "index": ti, "playing": -1}
                meters.append([0, 0])
                notes.append([])
                continue
            name, color, _, _, scenes = TRACKS[ti]
            on = playing and cur in scenes
            lv = self.level(BAND[name], st) if on else 0.0
            if name == "Lead" and on:
                lv = 0.35 * lv + 0.65 * self.breath_at(st)
            if name == "Lead Echo" and on:
                lv = 0.6 * lv
            pan = {"Hats": -0.3, "Keys": 0.15}.get(name, 0.0)
            meters.append([r(lv * (1 - max(0, pan)), 2), r(lv * (1 + min(0, pan)), 2)])
            nn = self.sounding(NOTES[name], st) if (on and NOTES[name]) else []
            notes.append(nn)
            slots = [self.slot(ti, si, cur, nxt) for si in range(SCENES)]
            if ti == cursor:
                for sl in slots:
                    sl["selected"] = sl["scene"] == max(cur, 0)
            keys[f"track/{ti}"] = {
                "exists": True, "name": name, "color": color, "mute": False, "solo": False,
                "mutedBySolo": False, "active": True, "volume": 0.79, "volumeText": "0.0 dB",
                "pan": r(0.5 + pan / 2), "panText": f"{pan:+.0%}" if pan else "C",
                "index": ti, "type": "Instrument", "group": False, "selected": ti == cursor,
                "armed": False, "monitor": "auto", "stopped": not on, "stopQueued": False,
                "playing": cur if on else -1, "slots": slots}
        m = self.s["master"]
        mi = int(st * self.fps)
        mm = m[mi] if playing and 0 <= mi < len(m) else [0, 0]
        keys["meters"] = {"tracks": meters, "fx": [], "master": [r(mm[0], 2), r(mm[1], 2)]}
        keys["notes"] = {"tracks": notes, "master": [n for tn in notes for n in tn][:32]}
        keys["mixer"] = {"master": {"exists": True, "name": "Master", "color": "#c0c0c0", "mute": False,
                                    "solo": False, "mutedBySolo": False, "active": True, "volume": 0.79,
                                    "volumeText": "0.0 dB", "pan": 0.5, "panText": "C"}, "fx": []}
        name, color, dev, preset, scenes = TRACKS[cursor]
        lv = meters[cursor][0]
        params = []
        for pi, (pname, base) in enumerate(PARAMS[dev]):
            val = base
            if dev == "JBreath":
                if pname == "Breath":
                    val = self.breath_at(st) if playing else 0
                if pname == "Unison":
                    val = 1.0 if sec_i == 4 else 0.0
                if pname == "Delay Mix":
                    val = 0.36 if name == "Lead Echo" else 0.14
                if pname == "Delay Feedback":
                    val = 0.55 if name == "Lead Echo" else 0.35
            mod = min(1.0, val + (0.25 * lv * math.sin(pi * 1.3 + 1) if pi % 3 == 0 else 0.0))
            text = f"{val * 100:.0f} %" if pname not in ("Unison",) else ("2 voices" if val > 0.5 else "1 voice")
            params.append({"exists": True, "name": pname, "value": r(val), "modulated": r(mod), "text": text})
        keys["device"] = {"exists": True, "track": name, "trackColor": color, "name": dev, "preset": preset,
                          "category": {"JKit": "Drums", "JSynth": "Synth", "JBreath": "Lead"}[dev],
                          "creator": "JClap", "enabled": True, "plugin": True, "windowOpen": False,
                          "pinned": False,
                          "page": {"index": 0, "name": "Main", "names": ["Main", "Mod", "FX"]},
                          "params": params,
                          "chain": [{"name": dev, "enabled": True, "selected": True},
                                    {"name": "EQ+", "enabled": True, "selected": False},
                                    {"name": "Compressor", "enabled": True, "selected": False}]}
        sec = self.sections[max(cur, 0)] if cur >= 0 else self.sections[0]
        into = max(0.0, beats - sec["bar"] * 4)
        clip_len = sec["bars"] * 4
        keys["clip"] = {"exists": True, "track": name, "scene": max(cur, 0),
                        "name": f"{name} {sec['name']}", "color": color, "playing": cur >= 0 and cur in scenes,
                        "playingStep": int(into * 4) if cur >= 0 else -1, "playStart": 0,
                        "loopStart": 0, "loopLength": clip_len, "loop": True}
        keys["markers"] = {"items": [{"name": s["name"], "position": s["bar"] * 4,
                                      "color": "#ffd84a" if i == cur else "#7f8ea3"}
                                     for i, s in enumerate(self.sections)]}
        return keys


class Tunnel:
    """The sender's side of JTunnel's state channel, on one UDP port."""

    MAGIC = b"JTUN"
    VERSION = 2
    PIECE = 1200

    def __init__(self, port=47251, host="127.0.0.1", stream_id=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.settimeout(0.0)
        self.receivers = set()
        self.stream_id = stream_id or (int(time.time()) & 0x7FFFFFFF)
        self.message_id = 0
        self.last = {}

    def poll(self):
        """Takes any subscribes waiting: each one adds its sender as a receiver."""
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
            except (BlockingIOError, socket.timeout):
                return
            if len(data) >= 6 and data[:4] == self.MAGIC and data[5] == 2:
                if addr not in self.receivers:
                    self.receivers.add(addr)
                    self.last = {}  # a new listener gets everything
            elif len(data) >= 6 and data[:4] == self.MAGIC and data[5] == 3:
                self.receivers.discard(addr)

    def wait_for_receiver(self, timeout=30.0):
        until = time.time() + timeout
        while not self.receivers and time.time() < until:
            self.poll()
            time.sleep(0.05)
        return bool(self.receivers)

    def packets(self, key, text):
        data = text.encode()
        pieces = max(1, math.ceil(len(data) / self.PIECE))
        if pieces > 64:
            raise ValueError(f"{key}: {len(data)} bytes is too long")
        self.message_id = (self.message_id + 1) & 0xFFFFFFFF
        kb = key.encode()
        for p in range(pieces):
            chunk = data[p * self.PIECE:(p + 1) * self.PIECE]
            yield (self.MAGIC + bytes([self.VERSION, 4])
                   + struct.pack("<IIBBB", self.stream_id, self.message_id, p, pieces, len(kb)) + kb
                   + struct.pack("<H", len(chunk)) + chunk)

    def send(self, keys, everything=False):
        """Sends each key whose message changed (or every key, with `everything`)."""
        self.poll()
        sent = 0
        for key, value in keys.items():
            text = json.dumps(value, separators=(",", ":"))
            if not everything and self.last.get(key) == text:
                continue
            self.last[key] = text
            for packet in self.packets(key, text):
                for addr in self.receivers:
                    self.sock.sendto(packet, addr)
            sent += 1
        return sent


if __name__ == "__main__":
    session = Session(sys.argv[1])
    tunnel = Tunnel(int(sys.argv[2]) if len(sys.argv) > 2 else 47251)
    print("waiting for a receiver's subscribe", flush=True)
    tunnel.wait_for_receiver(600)
    t0, refresh = time.time(), 0.0
    while True:
        t = time.time() - t0
        if t > session.end:
            break
        tunnel.send(session.state(t), everything=t - refresh > 1.0)
        if t - refresh > 1.0:
            refresh = t
        time.sleep(1 / 30)
