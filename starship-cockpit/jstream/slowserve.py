"""Serves the cockpit pages with their clock slowed by F, for a slow-motion capture.

Every .html response gets a script, first in <head>, that divides the time the page sees
(Date.now from a shared epoch, performance.now, and requestAnimationFrame's timestamp) by
F. Pages keep sharing one clock, as they do on the wall clock. With F=1 nothing changes.
"""
import http.server, os, sys, time
F = float(os.environ.get("SLOW", "1"))
E = int(os.environ.get("EPOCH", str(int(time.time() * 1000))))
ROOT = sys.argv[1]
JS = (f"<script>(()=>{{const F={F},E={E},rd=Date.now,rp=performance.now.bind(performance),"
      f"ra=window.requestAnimationFrame.bind(window);Date.now=()=>E+(rd()-E)/F;"
      f"performance.now=()=>rp()/F;window.requestAnimationFrame=cb=>ra(t=>cb(t/F));}})()</script>")
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=ROOT, **k)
    def log_message(s, *a): pass
    def end_headers(s):
        s.send_header("Cache-Control", "no-store"); super().end_headers()
    def do_GET(s):
        p = s.path.split("?")[0]
        if p.endswith(".html") and F != 1:
            fp = os.path.join(ROOT, p.lstrip("/"))
            if os.path.isfile(fp):
                b = open(fp, "rb").read().decode().replace("<head>", "<head>" + JS, 1).encode()
                s.send_response(200); s.send_header("Content-Type", "text/html; charset=utf-8")
                s.send_header("Content-Length", str(len(b))); s.end_headers(); s.wfile.write(b); return
        super().do_GET()
http.server.ThreadingHTTPServer(("127.0.0.1", 8767), H).serve_forever()
