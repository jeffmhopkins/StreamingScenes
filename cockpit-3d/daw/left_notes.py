"""Changes a cockpit already in a running JStream (a project imported before this) so the
left monitor's first soft key shows the notes page and the monitor starts on it, as
sources.py now builds it: the key that showed the transport (`left_transport`) becomes
`left_notes`, with its item, channel, sequence, hotkey (Ctrl+Alt+Shift+1) and lit key.

    python3 left_notes.py

NOTE=58 (the default) is the MIDI note on channel NOTE_CHANNEL (16) that played the old
key, which then plays the new one; NOTE= leaves the notes alone. JS_TOKEN and JS_MCP are
as for ../jstream/mcp.py.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "jstream"))

NOTE = os.environ.get("NOTE", "58")
NOTE_CHANNEL = int(os.environ.get("NOTE_CHANNEL", "16"))


def _gate(group):
    return {"modifier_id": f"switch_{group}", "property": "opacity", "enabled": True, "clock": "engine",
            "kind": "channel", "channel_id": "power_" + group, "smoothing_ms": 30, "curve": "linear",
            "from": -1.0, "to": 0.0}


def edits():
    import sources
    old = sources.SLOTS[0][0]
    new = sources.slots("left")[0][0]
    out = [{"type": "timeline.delete", "timeline_id": sources.sequence("left", old)},
           {"type": "item.remove", "item_id": sources.channel("left", old)},
           {"type": "item.remove", "item_id": "key_" + sources.channel("left", old)[4:]},
           {"type": "channel.delete", "channel_id": sources.channel("left", old)}]
    left = {sources.channel("left", s) for s, *_ in sources.slots("left")}
    keys = {"key_" + c[4:] for c in left}
    added = {sources.channel("left", new), "key_" + sources.channel("left", new)[4:]}
    for e in sources.edits(True, [_gate("glow"), _gate("master")]):
        t = e["type"]
        if t == "channel.set" and e["channel"]["channel_id"] in left:
            out.append(e)
        elif t == "item.add" and e["item_id"] in added:
            out.append(e)
        elif t in ("item.set_visible", "item.set_motion") and e["item_id"] in (left | keys) \
                and (t == "item.set_visible" or e["item_id"] in added):
            out.append(e)
        elif t == "timeline.set" and e["scene_id"] == "src_left":
            out.append(e)
        elif t == "hotkey.set" and e["action"].get("timeline_id") == sources.sequence("left", new):
            out.append(e)
    # The new key's item first in the subscene, where the old one was.
    out.append({"type": "item.reorder", "item_id": sources.channel("left", new), "index": 0})
    if NOTE:
        out.append({"type": "binding.set",
                    "trigger": {"kind": "midi_note", "note": int(NOTE), "channel": NOTE_CHANNEL},
                    "action": sources.action("left", new)})
    return out


if __name__ == "__main__":
    from mcp import batch, init
    init()
    _, ok = batch(edits(), "left monitor notes")
    print("done: the left monitor starts on the notes (Ctrl+Alt+Shift+1)" if ok else "FAILED")
