"""TEST HARNESS ONLY. A local mock portal with invented fixtures.

It exists to exercise the session-expiry failure path. It is not the real
portal, holds no real data, and produces no statistic that is reported as a
result. Bound to 127.0.0.1.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

FIXTURE = {"announcements": [{"id": 1}], "grades": [], "due_dates": [{"id": 7}]}


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json", headers=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        server = self.server
        server.hits += 1
        mode = server.mode
        if mode == "ok":
            self._send(200, json.dumps(FIXTURE))
        elif mode == "expired_error":
            self._send(200, json.dumps({"error": "Authentication required"}))
        elif mode == "redirect":
            self._send(302, "", headers={"Location": "/login"})
        elif mode == "nonjson":
            self._send(200, "<html>Please sign in</html>", ctype="text/html")
        elif mode == "flaky":
            if server.hits % 2 == 1:
                self._send(503, json.dumps({"error": "busy"}))
            else:
                self._send(200, json.dumps(FIXTURE))
        else:
            self._send(500, "{}")


class MockPortal:
    def __init__(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.mode = "ok"
        self.server.hits = 0
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d/api" % self.server.server_address[1]

    @property
    def hits(self):
        return self.server.hits

    def set_mode(self, mode):
        self.server.mode = mode

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
