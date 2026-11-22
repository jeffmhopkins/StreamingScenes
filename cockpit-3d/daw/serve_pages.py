"""Serves pages/ for the DAW screens: `python3 serve_pages.py [port]` (default 8765, on
127.0.0.1). The seven screens load at once, and `python -m http.server` accepts only 5
connections in its backlog, so one page could be refused for a whole render; this one
threads its requests and queues up to 128."""
import functools
import http.server
import os
import sys


class Server(http.server.ThreadingHTTPServer):
    request_queue_size = 128
    daemon_threads = True


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
pages = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=pages)
print(f"serving {pages} on http://127.0.0.1:{port}")
Server(("127.0.0.1", port), handler).serve_forever()
