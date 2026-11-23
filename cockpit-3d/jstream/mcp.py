"""A small client for JStream's MCP endpoint (streamable HTTP), for the scripts beside it.

JS_MCP is the endpoint (default http://127.0.0.1:4455/mcp) and JS_TOKEN the engine's
token file. Left out, it is the first that exists of `~/jstream-token` (the daemon as these
READMEs start it) and the desktop app's `token` in its data folder (`%APPDATA%\\JStream` on
Windows, as `jstream.exe --mcp` writes it). The session is closed on exit, since the daemon allows only a few at once.
"""
import atexit, base64, json, os, sys, urllib.request

URL = os.environ.get("JS_MCP", "http://127.0.0.1:4455/mcp")


def _token_file():
    if os.environ.get("JS_TOKEN"):
        return os.environ["JS_TOKEN"]
    tries = [os.path.expanduser("~/jstream-token")]
    if os.environ.get("APPDATA"):
        tries.append(os.path.join(os.environ["APPDATA"], "JStream", "token"))
    tries.append(os.path.expanduser("~/.local/share/jstream/token"))
    tries.append(os.path.expanduser("~/Library/Application Support/JStream/token"))
    for path in tries:
        if os.path.exists(path):
            return path
    sys.exit("no token file: set JS_TOKEN to the engine's token file (start the app with --mcp)")


TOKEN = open(_token_file()).read().strip()
S = {"sid": None, "id": 0}
W, H = 1920, 1080


def post(body):
    h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
         "Authorization": "Bearer " + TOKEN}
    if S["sid"]:
        h["Mcp-Session-Id"] = S["sid"]
    r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(), h), timeout=60)
    S["sid"] = r.headers.get("Mcp-Session-Id") or S["sid"]
    t = r.read().decode()
    if not t:
        return None
    if t.lstrip().startswith("data:") or "\ndata:" in t:
        t = [l[5:] for l in t.splitlines() if l.startswith("data:")][-1]
    return json.loads(t)


def init():
    post({"jsonrpc": "2.0", "id": 0, "method": "initialize",
          "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                     "clientInfo": {"name": "cockpit", "version": "1"}}})
    post({"jsonrpc": "2.0", "method": "notifications/initialized"})


def call(tool, args):
    S["id"] += 1
    return post({"jsonrpc": "2.0", "id": S["id"], "method": "tools/call",
                 "params": {"name": tool, "arguments": args}})


def text(r):
    if "error" in r:
        return "RPCERR " + json.dumps(r["error"])
    return "\n".join(c.get("text", "") for c in r["result"]["content"] if c["type"] == "text")


def _result(r, label, quiet=False):
    t = text(r)
    err = r.get("result", {}).get("isError") or t.startswith("RPCERR")
    if err and not quiet:
        print("FAIL", label, t[:1500], file=sys.stderr)
    return t, not err


def op(o, quiet=False, **kw):
    """Runs one protocol op through its noun's tool. Returns (text, ok). `quiet` doesn't
    print a refusal, for a probe whose failure is expected."""
    return _result(call(o["type"].split(".")[0], {"op": o, **kw}), o["type"], quiet)


def batch(edits, label=""):
    """Applies edits atomically. Returns (text, ok)."""
    return _result(call("batch", {"edits": edits}), "batch " + label)


def geo(x, y, w, h, **kw):
    g = {"center": {"x": x + w / 2, "y": y + h / 2}, "size": {"width": w, "height": h}}
    g.update(kw)
    return g


def asset(path):
    return {"type": "asset", "root": "absolute", "path": path}


def snap(path):
    r = call("video", {"op": {"type": "video.snapshot"}})
    for c in r["result"]["content"]:
        if c["type"] == "image":
            open(path, "wb").write(base64.b64decode(c["data"]))
            return True
    return False


def _close():
    if S["sid"]:
        try:
            urllib.request.urlopen(urllib.request.Request(
                URL, None, {"Authorization": "Bearer " + TOKEN, "Mcp-Session-Id": S["sid"]},
                method="DELETE"), timeout=10)
        except Exception:
            pass


atexit.register(_close)
